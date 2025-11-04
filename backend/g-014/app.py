import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import threading
import time
from flask import Flask, jsonify, request

from autoscaler.config import Config, load_config
from autoscaler.state import ClusterState
from autoscaler.gpu_pool_manager import GPUPoolManager
from autoscaler.autoscaler import AutoScaler
from autoscaler.load import LoadModel
from autoscaler.metrics import metrics_wsgi_app, update_metrics

app = Flask(__name__)

# Global singletons
CONFIG: Config = load_config(os.getenv("CONFIG_FILE", "config.yaml"))
STATE = ClusterState()
POOL_MANAGER = GPUPoolManager(config=CONFIG, state=STATE)
AUTOSCALER = AutoScaler(config=CONFIG, state=STATE, pool_manager=POOL_MANAGER)
LOAD = LoadModel()

_state_lock = threading.RLock()


def control_loop():
    tick_interval = CONFIG.loop_tick_seconds
    while True:
        time.sleep(tick_interval)
        with _state_lock:
            # Update spot preemptions
            POOL_MANAGER.tick()
            # Update metrics snapshot from load
            for dname, dep in list(STATE.deployments.items()):
                # if per-deployment load defined, use it; else, use global default
                rps = LOAD.get_rps(dname)
                dep.observed_rps = rps
            # Run autoscaler reconcile
            AUTOSCALER.reconcile()
            # Update metrics
            update_metrics(STATE)


@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})


@app.route("/state", methods=["GET"]) 
def state():
    with _state_lock:
        return jsonify(STATE.to_dict())


@app.route("/traffic", methods=["POST"]) 
def traffic():
    payload = request.get_json(force=True, silent=True) or {}
    rps = payload.get("rps")
    deployment = payload.get("deployment")
    if rps is None:
        return jsonify({"error": "missing rps"}), 400
    try:
        rps = float(rps)
    except Exception:
        return jsonify({"error": "invalid rps"}), 400
    with _state_lock:
        LOAD.set_rps(rps, deployment)
    return jsonify({"ok": True, "deployment": deployment or "_default_", "rps": rps})


@app.route("/deployments", methods=["POST"]) 
def create_deployment():
    payload = request.get_json(force=True, silent=True) or {}
    required = ["name", "target_rps_per_replica"]
    for k in required:
        if k not in payload:
            return jsonify({"error": f"missing {k}"}), 400
    with _state_lock:
        if payload["name"] in STATE.deployments:
            return jsonify({"error": "deployment exists"}), 409
        STATE.add_deployment(
            name=payload["name"],
            target_rps_per_replica=float(payload.get("target_rps_per_replica", 20.0)),
            min_replicas=int(payload.get("min_replicas", 0)),
            max_replicas=int(payload.get("max_replicas", 1000)),
            prefer_spot=bool(payload.get("prefer_spot", True)),
            spot_fraction_cap=float(payload.get("spot_fraction_cap", CONFIG.default_spot_fraction_cap)),
        )
    return jsonify({"ok": True})


@app.route("/deployments/<name>", methods=["DELETE"]) 
def delete_deployment(name: str):
    with _state_lock:
        if name not in STATE.deployments:
            return jsonify({"error": "not found"}), 404
        # remove pods
        STATE.remove_deployment(name)
    return jsonify({"ok": True})


@app.route("/scale/trigger", methods=["POST"]) 
def trigger_scale():
    with _state_lock:
        AUTOSCALER.reconcile()
        update_metrics(STATE)
    return jsonify({"ok": True})


@app.route("/config", methods=["GET"]) 
def get_config():
    return jsonify(CONFIG.to_dict())


@app.route("/config", methods=["POST"]) 
def set_config():
    payload = request.get_json(force=True, silent=True) or {}
    with _state_lock:
        CONFIG.update_from_dict(payload)
    return jsonify({"ok": True, "config": CONFIG.to_dict()})


# Mount metrics at /metrics using WSGI app
@app.route('/metrics')
def metrics():
    return metrics_wsgi_app()


if __name__ == "__main__":
    t = threading.Thread(target=control_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))



def create_app():
    return app


@app.route('/gpu/add', methods=['POST'])
def _auto_stub_gpu_add():
    return 'Auto-generated stub for /gpu/add', 200


@app.route('/gpu/list', methods=['GET'])
def _auto_stub_gpu_list():
    return 'Auto-generated stub for /gpu/list', 200


@app.route('/model/infer', methods=['POST'])
def _auto_stub_model_infer():
    return 'Auto-generated stub for /model/infer', 200
