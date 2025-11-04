import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import time
import threading
from flask import Flask, send_from_directory, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from ai_suggester import AICodeSuggester

app = Flask(__name__, static_folder="static", static_url_path="/static")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# In-memory document store with naive versioning
class DocStore:
    def __init__(self):
        self.docs = {}
        self.lock = threading.RLock()

    def _ensure(self, doc_id):
        if doc_id not in self.docs:
            self.docs[doc_id] = {
                "content": "",
                "version": 0,
                "users": {},  # sid -> {username, color, cursor}
                "updated_at": time.time()
            }

    def join(self, doc_id, sid, username, color):
        with self.lock:
            self._ensure(doc_id)
            self.docs[doc_id]["users"][sid] = {"username": username, "color": color, "cursor": 0}
            return {
                "content": self.docs[doc_id]["content"],
                "version": self.docs[doc_id]["version"],
                "users": self._public_users(doc_id)
            }

    def leave(self, sid):
        with self.lock:
            changed_docs = []
            for doc_id, doc in self.docs.items():
                if sid in doc["users"]:
                    del doc["users"][sid]
                    changed_docs.append(doc_id)
            return changed_docs

    def edit(self, doc_id, incoming_version, new_content):
        with self.lock:
            self._ensure(doc_id)
            doc = self.docs[doc_id]
            if incoming_version == doc["version"]:
                doc["content"] = new_content
                doc["version"] += 1
                doc["updated_at"] = time.time()
                return True, doc["version"], doc["content"]
            else:
                return False, doc["version"], doc["content"]

    def update_cursor(self, doc_id, sid, pos):
        with self.lock:
            self._ensure(doc_id)
            if sid in self.docs[doc_id]["users"]:
                self.docs[doc_id]["users"][sid]["cursor"] = int(max(0, pos))

    def get_state(self, doc_id):
        with self.lock:
            self._ensure(doc_id)
            doc = self.docs[doc_id]
            return {
                "content": doc["content"],
                "version": doc["version"],
                "users": self._public_users(doc_id)
            }

    def _public_users(self, doc_id):
        doc = self.docs[doc_id]
        return [
            {
                "id": sid,
                "username": uinfo["username"],
                "color": uinfo["color"],
                "cursor": uinfo.get("cursor", 0)
            }
            for sid, uinfo in doc["users"].items()
        ]

docs = DocStore()
suggester = AICodeSuggester()


def random_color(seed=None):
    import random
    rnd = random.Random(seed or os.urandom(4))
    r = rnd.randint(50, 200)
    g = rnd.randint(50, 200)
    b = rnd.randint(50, 200)
    return f"#{r:02x}{g:02x}{b:02x}"


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/api/suggest")
def api_suggest():
    try:
        body = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    code = body.get("code", "")
    cursor = int(body.get("cursorPos", len(code) or 0))
    language = (body.get("language") or "python").lower()
    hint = body.get("hint")

    try:
        suggestions = suggester.suggest(language=language, code=code, cursor=cursor, hint=hint)
        return jsonify({"suggestions": suggestions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@socketio.on("connect")
def on_connect():
    emit("connected", {"sid": request.sid})


@socketio.on("join_doc")
def on_join_doc(data):
    doc_id = (data or {}).get("doc_id") or "main"
    username = (data or {}).get("username") or f"user-{request.sid[:5]}"
    color = (data or {}).get("color") or random_color(request.sid)

    join_room(f"doc:{doc_id}")
    state = docs.join(doc_id, request.sid, username, color)
    emit("doc_state", {
        "doc_id": doc_id,
        "content": state["content"],
        "version": state["version"],
        "users": state["users"]
    })
    # Broadcast presence to others
    emit("presence", {"users": state["users"]}, to=f"doc:{doc_id}")


@socketio.on("edit")
def on_edit(data):
    doc_id = (data or {}).get("doc_id") or "main"
    content = (data or {}).get("content") or ""
    version = int((data or {}).get("version") or 0)

    ok, new_version, new_content = docs.edit(doc_id, version, content)
    if not ok:
        # Ask client to resync
        emit("sync", {"doc_id": doc_id, "content": new_content, "version": new_version})
        return

    # Broadcast update to all clients in room (including author)
    emit("update", {
        "doc_id": doc_id,
        "content": new_content,
        "version": new_version,
        "author": request.sid
    }, to=f"doc:{doc_id}")


@socketio.on("cursor")
def on_cursor(data):
    doc_id = (data or {}).get("doc_id") or "main"
    pos = int((data or {}).get("pos") or 0)
    docs.update_cursor(doc_id, request.sid, pos)

    # Send cursor announcement to others
    emit("cursor", {
        "sid": request.sid,
        "pos": pos
    }, to=f"doc:{doc_id}", skip_sid=request.sid)


@socketio.on("disconnect")
def on_disconnect():
    affected = docs.leave(request.sid)
    for doc_id in affected:
        state = docs.get_state(doc_id)
        emit("presence", {"users": state["users"]}, to=f"doc:{doc_id}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # In dev, Flask-SocketIO can run with threading
    socketio.run(app, host="0.0.0.0", port=port)



def create_app():
    return app
