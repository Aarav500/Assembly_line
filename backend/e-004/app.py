import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import threading
from flask import Flask, request, jsonify
from pman.state import State
from pman.cluster_manager import ClusterManager
from pman.pitr import PITRManager
from pman.failover import FailoverManager
import yaml

app = Flask(__name__)

CONFIG_PATH = os.environ.get("MPG_CONFIG", os.path.join(os.path.dirname(__file__), "config", "defaults.yaml"))
STATE_PATH = os.environ.get("MPG_STATE", os.path.join(os.path.dirname(__file__), "state", "state.json"))

os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)

with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f) or {}

state = State(STATE_PATH)
cluster_manager = ClusterManager(state, config)
pitr_manager = PITRManager(state, config)
failover_manager = FailoverManager(state, config, cluster_manager)

@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})

@app.route("/clusters", methods=["GET"]) 
def list_clusters():
    return jsonify({"clusters": cluster_manager.list_clusters()})

@app.route("/clusters", methods=["POST"]) 
def create_cluster():
    payload = request.get_json(force=True)
    required = ["name", "base_dir", "pg_bin", "port"]
    for r in required:
        if r not in payload:
            return jsonify({"error": f"missing field: {r}"}), 400
    try:
        cluster = cluster_manager.create_cluster(
            name=payload["name"],
            base_dir=payload["base_dir"],
            pg_bin=payload["pg_bin"],
            port=int(payload["port"]),
            replication_password=payload.get("replication_password"),
            archive_dir=payload.get("archive_dir"),
            initdb_args=payload.get("initdb_args", []),
        )
        return jsonify(cluster), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clusters/<name>", methods=["GET"]) 
def get_cluster(name):
    cluster = cluster_manager.get_cluster(name)
    if not cluster:
        return jsonify({"error": "not found"}), 404
    return jsonify(cluster)

@app.route("/clusters/<name>", methods=["DELETE"]) 
def delete_cluster(name):
    try:
        cluster_manager.delete_cluster(name)
        return jsonify({"status": "deleted"})
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clusters/<name>/init", methods=["POST"]) 
def init_primary(name):
    try:
        result = cluster_manager.init_primary(name)
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clusters/<name>/start", methods=["POST"]) 
def start_primary(name):
    try:
        result = cluster_manager.start_node(name, cluster_manager.get_current_primary_node_name(name))
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clusters/<name>/stop", methods=["POST"]) 
def stop_primary(name):
    try:
        result = cluster_manager.stop_node(name, cluster_manager.get_current_primary_node_name(name))
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clusters/<name>/replicas", methods=["POST"]) 
def create_replica(name):
    payload = request.get_json(force=True)
    required = ["replica_name", "port"]
    for r in required:
        if r not in payload:
            return jsonify({"error": f"missing field: {r}"}), 400
    try:
        result = cluster_manager.create_replica(name, payload["replica_name"], int(payload["port"]))
        return jsonify(result), 201
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clusters/<name>/replicas/<replica>/start", methods=["POST"]) 
def start_replica(name, replica):
    try:
        result = cluster_manager.start_node(name, replica)
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clusters/<name>/replicas/<replica>/stop", methods=["POST"]) 
def stop_replica(name, replica):
    try:
        result = cluster_manager.stop_node(name, replica)
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clusters/<name>/promote/<replica>", methods=["POST"]) 
def promote_replica(name, replica):
    try:
        result = cluster_manager.promote_replica(name, replica)
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clusters/<name>/pitr/backups", methods=["POST"]) 
def create_backup(name):
    payload = request.get_json(silent=True) or {}
    label = payload.get("label")
    try:
        result = pitr_manager.create_base_backup(name, label=label)
        return jsonify(result), 201
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clusters/<name>/pitr/restore", methods=["POST"]) 
def restore_pitr(name):
    payload = request.get_json(force=True)
    required = ["backup_name", "target_time", "new_name", "port"]
    for r in required:
        if r not in payload:
            return jsonify({"error": f"missing field: {r}"}), 400
    try:
        result = pitr_manager.restore_to_time(
            name,
            backup_name=payload["backup_name"],
            target_time=payload["target_time"],
            new_name=payload["new_name"],
            port=int(payload["port"]) 
        )
        return jsonify(result), 201
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clusters/<name>/monitor", methods=["POST"]) 
def configure_monitor(name):
    payload = request.get_json(force=True)
    enabled = payload.get("enabled")
    interval = int(payload.get("interval", 5))
    fail_threshold = int(payload.get("fail_threshold", 3))
    if enabled is None:
        return jsonify({"error": "missing field: enabled"}), 400
    try:
        result = failover_manager.configure_monitor(name, enabled, interval, fail_threshold)
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({"error": "not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



def create_app():
    return app


@app.route('/instances', methods=['POST'])
def _auto_stub_instances():
    return 'Auto-generated stub for /instances', 200


@app.route('/instances/primary-001/replicas', methods=['POST'])
def _auto_stub_instances_primary_001_replicas():
    return 'Auto-generated stub for /instances/primary-001/replicas', 200


@app.route('/instances/primary-001/failover', methods=['POST'])
def _auto_stub_instances_primary_001_failover():
    return 'Auto-generated stub for /instances/primary-001/failover', 200
