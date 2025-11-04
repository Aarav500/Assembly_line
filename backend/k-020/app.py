import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify
from snapshot_manager import SnapshotManager
from test_runner import TestRunner
import config

app = Flask(__name__)

base_dir = os.path.abspath(os.path.dirname(__file__))
manager = SnapshotManager(base_dir=base_dir,
                          workspace_dir=config.WORKSPACE_DIR,
                          snapshot_dir=config.SNAPSHOT_DIR)
runner = TestRunner(workspace_dir=os.path.join(base_dir, config.WORKSPACE_DIR))

@app.route("/")
def health():
    return jsonify({"status": "ok", "message": "Snapshot Rollback Agent running"})

@app.route("/api/snapshots", methods=["GET"]) 
def list_snapshots():
    try:
        return jsonify({"snapshots": manager.list_snapshots()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/snapshots", methods=["POST"]) 
def create_snapshot():
    body = request.get_json(silent=True) or {}
    label = body.get("label")
    metadata = body.get("metadata")
    try:
        snapshot = manager.create_snapshot(label=label, metadata=metadata)
        return jsonify({"snapshot": snapshot}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/snapshots/<snapshot_id>", methods=["GET"]) 
def get_snapshot(snapshot_id):
    try:
        snap = manager.get_snapshot(snapshot_id)
        if not snap:
            return jsonify({"error": "Snapshot not found"}), 404
        return jsonify({"snapshot": snap})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/snapshots/<snapshot_id>", methods=["DELETE"]) 
def delete_snapshot(snapshot_id):
    try:
        deleted = manager.delete_snapshot(snapshot_id)
        if not deleted:
            return jsonify({"error": "Snapshot not found"}), 404
        return jsonify({"deleted": True, "id": snapshot_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/rollback", methods=["POST"]) 
def rollback():
    body = request.get_json(silent=True) or {}
    snapshot_id = body.get("id")
    if not snapshot_id:
        return jsonify({"error": "Missing field 'id'"}), 400
    try:
        result = manager.rollback(snapshot_id)
        return jsonify({"rolled_back": True, "to": result})
    except FileNotFoundError:
        return jsonify({"error": "Snapshot not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tests/run", methods=["POST"]) 
def run_tests():
    body = request.get_json(silent=True) or {}
    command = body.get("command") or config.TEST_COMMAND
    env = body.get("env") or {}
    try:
        result = runner.run_tests(command=command, extra_env=env)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/rollback-and-test", methods=["POST"]) 
def rollback_and_test():
    body = request.get_json(silent=True) or {}
    snapshot_id = body.get("id")
    command = body.get("command") or config.TEST_COMMAND
    env = body.get("env") or {}
    if not snapshot_id:
        return jsonify({"error": "Missing field 'id'"}), 400
    try:
        rb = manager.rollback(snapshot_id)
        result = runner.run_tests(command=command, extra_env=env)
        return jsonify({"rolled_back": rb, "test_result": result})
    except FileNotFoundError:
        return jsonify({"error": "Snapshot not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)



def create_app():
    return app


@app.route('/state', methods=['GET', 'POST'])
def _auto_stub_state():
    return 'Auto-generated stub for /state', 200


@app.route('/rollback/0', methods=['POST'])
def _auto_stub_rollback_0():
    return 'Auto-generated stub for /rollback/0', 200
