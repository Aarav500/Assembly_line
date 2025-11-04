from typing import Any, Dict, Iterable, List, Optional, Tuple
from flask import request, session
from flask_socketio import emit, join_room as sio_join_room, leave_room as sio_leave_room
from .extensions import socketio, redis_client

# Redis keys
ONLINE_USERS_KEY = "presence:online_users"
USER_SIDS_KEY = "presence:user:{user_id}:sids"
SID_USER_KEY = "presence:sid:{sid}:user"
SID_ROOMS_KEY = "presence:sid:{sid}:rooms"
ROOM_USERS_KEY = "presence:room:{room}:users"

# Utility functions

def _user_sids_key(user_id: str) -> str:
    return USER_SIDS_KEY.format(user_id=user_id)


def _sid_user_key(sid: str) -> str:
    return SID_USER_KEY.format(sid=sid)


def _sid_rooms_key(sid: str) -> str:
    return SID_ROOMS_KEY.format(sid=sid)


def _room_users_key(room: str) -> str:
    return ROOM_USERS_KEY.format(room=room)


def _user_room_name(user_id: str) -> str:
    return f"user:{user_id}"


def _get_user_id_from_auth(auth: Optional[Dict[str, Any]]) -> Optional[str]:
    # Priority: auth dict -> query args -> Authorization header (Bearer <user_id>)
    if auth and isinstance(auth, dict):
        if "user_id" in auth and auth["user_id"]:
            return str(auth["user_id"])
        if "token" in auth and auth["token"]:
            return str(auth["token"])  # demo: treat token as user_id
    args = request.args or {}
    if "user_id" in args and args.get("user_id"):
        return str(args.get("user_id"))
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1]
    return None


def _broadcast_user_online(user_id: str) -> None:
    socketio.emit("presence:user_online", {"user_id": user_id})


def _broadcast_user_offline(user_id: str) -> None:
    socketio.emit("presence:user_offline", {"user_id": user_id})


def _broadcast_room_join(room: str, user_id: str) -> None:
    socketio.emit("presence:room_join", {"room": room, "user_id": user_id}, room=room)


def _broadcast_room_leave(room: str, user_id: str) -> None:
    socketio.emit("presence:room_leave", {"room": room, "user_id": user_id}, room=room)


def _user_became_online_after_add(user_id: str, sid: str) -> bool:
    pipe = redis_client.pipeline()
    pipe.sadd(_user_sids_key(user_id), sid)
    pipe.scard(_user_sids_key(user_id))
    added, count = pipe.execute()
    if count == 1:
        redis_client.sadd(ONLINE_USERS_KEY, user_id)
        return True
    return False


def _user_became_offline_after_remove(user_id: str, sid: str) -> bool:
    pipe = redis_client.pipeline()
    pipe.srem(_user_sids_key(user_id), sid)
    pipe.scard(_user_sids_key(user_id))
    removed, count = pipe.execute()
    if count == 0:
        redis_client.srem(ONLINE_USERS_KEY, user_id)
        return True
    return False


def _ensure_user_in_room_set(room: str, user_id: str) -> bool:
    # Returns True if user newly added to room presence
    return bool(redis_client.sadd(_room_users_key(room), user_id))


def _remove_user_from_room_if_no_sid_remains(room: str, user_id: str, exclude_sid: Optional[str] = None) -> bool:
    # Check if any of the user's sids still in the room; if none, remove from room set. Returns True if removed.
    user_sids = redis_client.smembers(_user_sids_key(user_id))
    if exclude_sid:
        user_sids.discard(exclude_sid)
    if not user_sids:
        removed = bool(redis_client.srem(_room_users_key(room), user_id))
        return removed
    pipe = redis_client.pipeline()
    for s in user_sids:
        pipe.sismember(_sid_rooms_key(s), room)
    results = pipe.execute()
    if any(results):
        return False
    return bool(redis_client.srem(_room_users_key(room), user_id))


@socketio.on("connect")
def on_connect(auth):
    user_id = _get_user_id_from_auth(auth)
    if not user_id:
        return False  # reject connection
    sid = request.sid
    session["user_id"] = user_id

    # Map sid->user
    redis_client.set(_sid_user_key(sid), user_id)

    became_online = _user_became_online_after_add(user_id, sid)

    # Join personal room for direct messages
    user_room = _user_room_name(user_id)
    sio_join_room(user_room)

    emit("connected", {"sid": sid, "user_id": user_id, "user_room": user_room})

    if became_online:
        _broadcast_user_online(user_id)


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    user_id = session.get("user_id") or redis_client.get(_sid_user_key(sid))

    # Clean sid rooms and update room presence
    sid_rooms_key = _sid_rooms_key(sid)
    rooms = set(redis_client.smembers(sid_rooms_key))

    for room in rooms:
        redis_client.srem(sid_rooms_key, room)
        removed = _remove_user_from_room_if_no_sid_remains(room, user_id, exclude_sid=sid)
        if removed:
            _broadcast_room_leave(room, user_id)

    # Remove mapping and update user presence
    redis_client.delete(_sid_user_key(sid))

    if user_id:
        became_offline = _user_became_offline_after_remove(user_id, sid)
        if became_offline:
            _broadcast_user_offline(user_id)


@socketio.on("join_room")
def on_join_room(data: Dict[str, Any]):
    user_id = session.get("user_id")
    if not user_id:
        emit("error", {"error": "unauthorized"})
        return

    if not data:
        emit("error", {"error": "invalid_payload"})
        return

    rooms: List[str] = []
    if isinstance(data, dict):
        if "room" in data and data["room"]:
            rooms = [str(data["room"])]
        elif "rooms" in data and isinstance(data["rooms"], list):
            rooms = [str(r) for r in data["rooms"] if r]
    if not rooms:
        emit("error", {"error": "no_rooms_specified"})
        return

    sid = request.sid
    for room in rooms:
        sio_join_room(room)
        redis_client.sadd(_sid_rooms_key(sid), room)
        newly_added = _ensure_user_in_room_set(room, user_id)
        emit("room_joined", {"room": room})
        if newly_added:
            _broadcast_room_join(room, user_id)


@socketio.on("leave_room")
def on_leave_room(data: Dict[str, Any]):
    user_id = session.get("user_id")
    if not user_id:
        emit("error", {"error": "unauthorized"})
        return

    room = None
    if isinstance(data, dict):
        room = data.get("room")
    if not room:
        emit("error", {"error": "no_room_specified"})
        return

    sio_leave_room(room)
    sid = request.sid
    redis_client.srem(_sid_rooms_key(sid), room)
    removed = _remove_user_from_room_if_no_sid_remains(room, user_id, exclude_sid=None)
    emit("room_left", {"room": room})
    if removed:
        _broadcast_room_leave(room, user_id)


@socketio.on("notify_user")
def on_notify_user(data: Dict[str, Any]):
    user_id = session.get("user_id")
    if not user_id:
        emit("error", {"error": "unauthorized"})
        return

    if not isinstance(data, dict) or not data.get("to_user_id"):
        emit("error", {"error": "invalid_payload"})
        return

    to_user_id = str(data["to_user_id"])
    payload = data.get("payload", {})
    event_name = data.get("event", "notification")

    target_room = _user_room_name(to_user_id)
    socketio.emit(event_name, {"from": user_id, "to": to_user_id, "payload": payload}, room=target_room)
    emit("notify_user:ack", {"to_user_id": to_user_id, "event": event_name})


@socketio.on("notify_room")
def on_notify_room(data: Dict[str, Any]):
    user_id = session.get("user_id")
    if not user_id:
        emit("error", {"error": "unauthorized"})
        return

    if not isinstance(data, dict) or not data.get("room"):
        emit("error", {"error": "invalid_payload"})
        return

    room = str(data["room"])
    payload = data.get("payload", {})
    event_name = data.get("event", "notification")

    socketio.emit(event_name, {"from": user_id, "room": room, "payload": payload}, room=room)
    emit("notify_room:ack", {"room": room, "event": event_name})


@socketio.on("broadcast_update")
def on_broadcast_update(data: Dict[str, Any]):
    user_id = session.get("user_id")
    if not user_id:
        emit("error", {"error": "unauthorized"})
        return

    payload = data if isinstance(data, dict) else {"data": data}
    socketio.emit("update", {"from": user_id, **payload})
    emit("broadcast_update:ack", {"ok": True})


@socketio.on("typing")
def on_typing(data: Dict[str, Any]):
    user_id = session.get("user_id")
    if not user_id:
        emit("error", {"error": "unauthorized"})
        return

    if not isinstance(data, dict) or not data.get("room"):
        emit("error", {"error": "invalid_payload"})
        return

    room = str(data["room"])
    typing = bool(data.get("typing", True))
    socketio.emit(
        "typing",
        {"room": room, "user_id": user_id, "typing": typing},
        room=room,
        include_self=False,
    )


@socketio.on("whoami")
def on_whoami():
    user_id = session.get("user_id")
    emit("whoami:result", {"user_id": user_id, "sid": request.sid})


@socketio.on("heartbeat")
def on_heartbeat(data=None):
    emit("heartbeat:ack", {"ts": socketio.server.manager.get_server().eio.current_time()})

