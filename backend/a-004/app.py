import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import signal
import logging
from flask import Flask, jsonify, request
from manager import WatcherManager

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("repo-folder-sync-watcher")

app = Flask(__name__)
manager = WatcherManager()

@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})

@app.route("/watchers", methods=["GET"]) 
def list_watchers():
    return jsonify({
        "watchers": [w.to_dict() for w in manager.list_watchers()]
    })

@app.route("/watchers", methods=["POST"]) 
def add_watcher():
    data = request.get_json(force=True, silent=True) or {}
    path = data.get("path")
    if not path:
        return jsonify({"error": "path is required"}), 400
    debounce_seconds = float(data.get("debounce_seconds", 2.0))
    remote = data.get("remote")
    branch = data.get("branch")
    auto_push = bool(data.get("auto_push", True))
    auto_init = bool(data.get("auto_init", False))

    try:
        watcher = manager.add_watcher(
            path=path,
            debounce_seconds=debounce_seconds,
            remote=remote,
            branch=branch,
            auto_push=auto_push,
            auto_init=auto_init,
        )
        return jsonify({"id": watcher.id, "watcher": watcher.to_dict()}), 201
    except Exception as e:
        logger.exception("Failed to add watcher")
        return jsonify({"error": str(e)}), 400

@app.route("/watchers/<watcher_id>", methods=["DELETE"]) 
def delete_watcher(watcher_id):
    ok = manager.remove_watcher(watcher_id)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "removed", "id": watcher_id})

@app.route("/watchers/<watcher_id>", methods=["GET"]) 
def get_watcher(watcher_id):
    watcher = manager.get_watcher(watcher_id)
    if not watcher:
        return jsonify({"error": "not found"}), 404
    return jsonify(watcher.to_dict())

@app.route("/watchers/<watcher_id>/sync", methods=["POST"]) 
def force_sync(watcher_id):
    watcher = manager.get_watcher(watcher_id)
    if not watcher:
        return jsonify({"error": "not found"}), 404
    try:
        result = watcher.force_sync()
        return jsonify({"status": "ok", "result": result})
    except Exception as e:
        logger.exception("Force sync failed")
        return jsonify({"error": str(e)}), 500

@app.route("/watchers/<watcher_id>/pull", methods=["POST"]) 
def pull(watcher_id):
    watcher = manager.get_watcher(watcher_id)
    if not watcher:
        return jsonify({"error": "not found"}), 404
    try:
        result = watcher.pull()
        return jsonify({"status": "ok", "result": result})
    except Exception as e:
        logger.exception("Pull failed")
        return jsonify({"error": str(e)}), 500

@app.route("/watchers/<watcher_id>/pause", methods=["POST"]) 
def pause(watcher_id):
    watcher = manager.get_watcher(watcher_id)
    if not watcher:
        return jsonify({"error": "not found"}), 404
    watcher.pause()
    return jsonify({"status": "paused", "id": watcher_id})

@app.route("/watchers/<watcher_id>/resume", methods=["POST"]) 
def resume(watcher_id):
    watcher = manager.get_watcher(watcher_id)
    if not watcher:
        return jsonify({"error": "not found"}), 404
    watcher.resume()
    return jsonify({"status": "resumed", "id": watcher_id})


def init_from_env():
    paths = os.getenv("WATCH_PATHS")
    if not paths:
        return
    remote = os.getenv("GIT_REMOTE", None)
    branch = os.getenv("GIT_BRANCH", None)
    debounce = float(os.getenv("DEBOUNCE_SECONDS", "2.0"))
    auto_push = os.getenv("AUTO_PUSH", "true").lower() in ("1", "true", "yes", "on")
    auto_init = os.getenv("AUTO_INIT", "false").lower() in ("1", "true", "yes", "on")

    for raw in paths.split(","):
        p = raw.strip()
        if not p:
            continue
        try:
            manager.add_watcher(
                path=p,
                debounce_seconds=debounce,
                remote=remote,
                branch=branch,
                auto_push=auto_push,
                auto_init=auto_init,
            )
            logger.info("Watching %s", p)
        except Exception:
            logger.exception("Failed to init watcher for %s", p)


def shutdown(*_):
    logger.info("Shutting down watchers...")
    manager.stop_all()


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

if __name__ == "__main__":
    init_from_env()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    app.run(host=host, port=port)



def create_app():
    return app
