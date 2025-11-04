import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import threading
from collections import defaultdict

from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sock import Sock

app = Flask(__name__, static_folder="static", static_url_path="/static")
socketio = SocketIO(app, cors_allowed_origins="*")
sock = Sock(app)

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.get("/api/ping")
def ping():
    return jsonify({"status": "ok"})

# ---------- Raw WebSocket (Flask-Sock) ----------
ws_clients = set()
ws_lock = threading.Lock()

@sock.route("/ws")
def websocket_endpoint(ws):
    with ws_lock:
        ws_clients.add(ws)
    try:
        ws.send(json.dumps({"type": "system", "message": "Connected to Flask WebSocket endpoint."}))
        while True:
            data = ws.receive()
            if data is None:
                break
            # Try parse JSON, otherwise wrap as text
            try:
                parsed = json.loads(data)
                message = parsed.get("message", data)
            except Exception:
                message = data

            payload_self = json.dumps({"type": "echo", "message": message})
            payload_broadcast = json.dumps({"type": "broadcast", "message": message})

            dead = []
            with ws_lock:
                for client in list(ws_clients):
                    try:
                        if client is ws:
                            client.send(payload_self)
                        else:
                            client.send(payload_broadcast)
                    except Exception:
                        dead.append(client)
                for d in dead:
                    ws_clients.discard(d)
    finally:
        with ws_lock:
            ws_clients.discard(ws)

# ---------- Socket.IO (Flask-SocketIO) ----------

# Simple chat events
@socketio.on("connect")
def on_connect():
    emit("system", {"message": "Connected", "sid": request.sid})

@socketio.on("disconnect")
def on_disconnect():
    _cleanup_webrtc_rooms_for_sid(request.sid)

@socketio.on("join")
def sio_join(data):
    room = (data or {}).get("room")
    if not room:
        emit("error", {"message": "room is required"})
        return
    join_room(room)
    emit("system", {"message": f"{request.sid} joined {room}", "room": room}, room=room)

@socketio.on("leave")
def sio_leave(data):
    room = (data or {}).get("room")
    if not room:
        emit("error", {"message": "room is required"})
        return
    leave_room(room)
    emit("system", {"message": f"{request.sid} left {room}", "room": room}, room=room)

@socketio.on("chat_message")
def sio_chat_message(data):
    room = (data or {}).get("room")
    message = (data or {}).get("message")
    if not room:
        emit("error", {"message": "room is required"})
        return
    emit("chat_message", {"sid": request.sid, "message": message}, room=room)

# ---------- WebRTC Signaling over Socket.IO ----------
# We implement a simple mesh signaling where each peer holds a PeerConnection per other peer.
# Events: webrtc_join, webrtc_leave, webrtc_offer, webrtc_answer, webrtc_ice_candidate

_webrtc_rooms = defaultdict(set)
_webrtc_lock = threading.Lock()


def _cleanup_webrtc_rooms_for_sid(sid: str):
    with _webrtc_lock:
        rooms_to_notify = []
        for room, sids in list(_webrtc_rooms.items()):
            if sid in sids:
                sids.discard(sid)
                rooms_to_notify.append(room)
            if not sids:
                _webrtc_rooms.pop(room, None)
    # Notify peers that a sid left
    for room in rooms_to_notify:
        socketio.emit("webrtc_peer_left", {"sid": sid, "room": room}, room=room)


@socketio.on("webrtc_join")
def webrtc_join(data):
    room = (data or {}).get("room")
    if not room:
        emit("error", {"message": "room is required"})
        return
    join_room(room)
    with _webrtc_lock:
        peers = [s for s in _webrtc_rooms[room] if s != request.sid]
        _webrtc_rooms[room].add(request.sid)
    # Send list of existing peers to the new joiner
    emit("webrtc_peers", {"peers": peers, "room": room}, to=request.sid)
    # Inform others that a new peer joined (optional informational)
    emit("webrtc_peer_joined", {"sid": request.sid, "room": room}, room=room, include_self=False)


@socketio.on("webrtc_leave")
def webrtc_leave(data):
    room = (data or {}).get("room")
    if not room:
        emit("error", {"message": "room is required"})
        return
    leave_room(room)
    with _webrtc_lock:
        if room in _webrtc_rooms and request.sid in _webrtc_rooms[room]:
            _webrtc_rooms[room].discard(request.sid)
            if not _webrtc_rooms[room]:
                _webrtc_rooms.pop(room, None)
    emit("webrtc_peer_left", {"sid": request.sid, "room": room}, room=room)


@socketio.on("webrtc_offer")
def webrtc_offer(data):
    target = (data or {}).get("to")
    sdp = (data or {}).get("sdp")
    room = (data or {}).get("room")
    if not target or not sdp:
        emit("error", {"message": "to and sdp are required"})
        return
    emit("webrtc_offer", {"from": request.sid, "sdp": sdp, "room": room}, to=target)


@socketio.on("webrtc_answer")
def webrtc_answer(data):
    target = (data or {}).get("to")
    sdp = (data or {}).get("sdp")
    room = (data or {}).get("room")
    if not target or not sdp:
        emit("error", {"message": "to and sdp are required"})
        return
    emit("webrtc_answer", {"from": request.sid, "sdp": sdp, "room": room}, to=target)


@socketio.on("webrtc_ice_candidate")
def webrtc_ice_candidate(data):
    target = (data or {}).get("to")
    candidate = (data or {}).get("candidate")
    room = (data or {}).get("room")
    if not target or candidate is None:
        emit("error", {"message": "to and candidate are required"})
        return
    emit("webrtc_ice_candidate", {"from": request.sid, "candidate": candidate, "room": room}, to=target)


if __name__ == "__main__":
    # Using SocketIO's run to support WebSocket and Socket.IO in one server
    socketio.run(app, host="0.0.0.0", port=5000)



def create_app():
    return app


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200
