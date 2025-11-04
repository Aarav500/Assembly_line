from typing import Any, Dict
from flask import Blueprint, jsonify, request
from .extensions import socketio, redis_client
from .events import ONLINE_USERS_KEY, _room_users_key

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/presence/online")
def presence_online():
    users = sorted(redis_client.smembers(ONLINE_USERS_KEY))
    return jsonify({"online_users": users})


@api_bp.get("/presence/room/<room>")
def presence_room(room: str):
    users = sorted(redis_client.smembers(_room_users_key(room)))
    return jsonify({"room": room, "users": users})


@api_bp.post("/notify")
def notify_via_http():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    # Accept payload: {"to_user_id": "...", "room": "...", "event": "notification", "payload": {...}}
    event_name = data.get("event", "notification")
    payload = data.get("payload", {})

    if data.get("to_user_id"):
        to_user_id = str(data["to_user_id"])
        socketio.emit(event_name, {"from": "server", "to": to_user_id, "payload": payload}, room=f"user:{to_user_id}")
        return jsonify({"status": "sent", "target": f"user:{to_user_id}", "event": event_name})
    if data.get("room"):
        room = str(data["room"])
        socketio.emit(event_name, {"from": "server", "room": room, "payload": payload}, room=room)
        return jsonify({"status": "sent", "target": room, "event": event_name})

    return jsonify({"error": "must specify to_user_id or room"}), 400

