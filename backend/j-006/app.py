import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import threading
from flask import Flask, jsonify, request, send_from_directory, render_template, abort
from debug_session import session_manager, PROJECT_ROOT, safe_relpath
from test_discovery import discover_tests, get_test_callable

app = Flask(__name__, static_folder="static", template_folder="templates")

# In-memory cache for discovered tests
_DISCOVERED = None
_DISCOVER_LOCK = threading.Lock()


def ensure_discovered():
    global _DISCOVERED
    with _DISCOVER_LOCK:
        if _DISCOVERED is None:
            _DISCOVERED = discover_tests()
    return _DISCOVERED


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/tests", methods=["GET"]) 
def api_tests():
    tests = ensure_discovered()
    return jsonify({"tests": tests})


@app.route("/api/run", methods=["POST"]) 
def api_run():
    data = request.get_json(silent=True) or {}
    test_id = data.get("test_id")
    if not test_id:
        return jsonify({"error": "test_id required"}), 400

    tests = ensure_discovered()
    test_meta = next((t for t in tests if t["id"] == test_id), None)
    if not test_meta:
        return jsonify({"error": "Unknown test_id"}), 404

    try:
        target_callable, origin = get_test_callable(test_meta)
    except Exception as e:
        return jsonify({"error": f"Failed to load test: {e}"}), 500

    sess = session_manager.create_session(target_callable, origin)
    return jsonify({"session_id": sess.session_id, "origin": origin})


@app.route("/api/state", methods=["GET"]) 
def api_state():
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    sess = session_manager.get_session(session_id)
    if not sess:
        return jsonify({"error": "Unknown session_id"}), 404
    return jsonify(sess.get_state())


@app.route("/api/command", methods=["POST"]) 
def api_command():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    action = data.get("action")
    if not session_id or not action:
        return jsonify({"error": "session_id and action required"}), 400
    sess = session_manager.get_session(session_id)
    if not sess:
        return jsonify({"error": "Unknown session_id"}), 404

    ok, msg = sess.command(action)
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"ok": True})


@app.route("/api/stop", methods=["POST"]) 
def api_stop():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    sess = session_manager.get_session(session_id)
    if not sess:
        return jsonify({"error": "Unknown session_id"}), 404
    sess.stop()
    return jsonify({"ok": True})


@app.route("/api/breakpoints", methods=["POST"]) 
def api_breakpoints():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    file_path = data.get("file")
    line = data.get("line")
    op = data.get("op")
    if not session_id or not file_path or not isinstance(line, int) or op not in ("add", "remove"):
        return jsonify({"error": "session_id, file, line (int), op (add/remove) required"}), 400
    sess = session_manager.get_session(session_id)
    if not sess:
        return jsonify({"error": "Unknown session_id"}), 404

    abs_file = os.path.abspath(os.path.join(PROJECT_ROOT, file_path))
    if not abs_file.startswith(PROJECT_ROOT):
        return jsonify({"error": "Invalid file path"}), 400

    if op == "add":
        ok, msg = sess.add_breakpoint(abs_file, line)
    else:
        ok, msg = sess.remove_breakpoint(abs_file, line)
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"ok": True, "breakpoints": sess.list_breakpoints()})


@app.route("/api/file", methods=["GET"]) 
def api_file():
    path = request.args.get("path")
    if not path:
        return jsonify({"error": "path required"}), 400
    abs_path = os.path.abspath(os.path.join(PROJECT_ROOT, path))
    if not abs_path.startswith(PROJECT_ROOT):
        return jsonify({"error": "Invalid path"}), 400
    if not os.path.exists(abs_path):
        return jsonify({"error": "File not found"}), 404
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        return jsonify({"path": safe_relpath(abs_path), "lines": lines})
    except Exception as e:
        return jsonify({"error": f"Failed to read file: {e}"}), 500


@app.route("/api/snapshots", methods=["GET"]) 
def api_snapshots():
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    sess = session_manager.get_session(session_id)
    if not sess:
        return jsonify({"error": "Unknown session_id"}), 404
    snaps = sess.list_snapshots()
    return jsonify({"snapshots": snaps})


@app.route("/api/snapshots/<int:snap_id>", methods=["GET"]) 
def api_snapshot_detail(snap_id):
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    sess = session_manager.get_session(session_id)
    if not sess:
        return jsonify({"error": "Unknown session_id"}), 404
    snap = sess.get_snapshot(snap_id)
    if not snap:
        return jsonify({"error": "Snapshot not found"}), 404
    return jsonify(snap)


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)


if __name__ == "__main__":
    # Enable auto-reload in development
    app.run(host="127.0.0.1", port=5000, debug=True)



def create_app():
    return app
