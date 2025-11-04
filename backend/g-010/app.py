import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
import json
import random
import threading
from flask import Flask, request, jsonify

from canary.controller import CanaryController
from canary.router import TrafficRouter
from metrics.collector import MetricsCollector
from models.v1 import ModelV1
from models.v2 import ModelV2


def create_app():
    app = Flask(__name__)

    # Initialize models registry
    models = {
        "v1": ModelV1(),
        "v2": ModelV2(error_prob=float(os.getenv("MODEL_V2_ERROR_PROB", "0.05"))),
    }

    metrics = MetricsCollector(max_latency_samples=2000)
    controller = CanaryController(state_path=os.getenv("STATE_PATH", "state.json"))
    router = TrafficRouter(controller=controller, models=models)

    # Start controller monitor thread for auto canary evaluation
    controller.start_monitor(metrics)

    @app.route("/predict", methods=["POST"])
    def predict():
        started = time.time()
        payload = request.get_json(silent=True) or {}
        text = payload.get("text", "")
        user_id = request.headers.get("X-User-Id")
        force_version = request.headers.get("X-Force-Model-Version")

        version = router.choose_version(force_version=force_version, user_id=user_id)
        model = models.get(version)
        status = 200
        result = None
        error = None
        try:
            result = model.predict(text)
        except Exception as e:
            status = 500
            error = str(e)
        finally:
            latency_ms = (time.time() - started) * 1000.0
            metrics.record(version=version, success=(status == 200), latency_ms=latency_ms)

        debug = request.args.get("debug") == "1"
        response = {
            "version": version,
            "latency_ms": round((time.time() - started) * 1000.0, 2),
            "ok": status == 200,
        }
        if status == 200:
            response["output"] = result
        else:
            response["error"] = error

        if debug:
            response["canary_state"] = controller.get_state()
            response["metrics_snapshot"] = metrics.snapshot()

        return jsonify(response), status

    @app.route("/metrics", methods=["GET"])
    def get_metrics():
        snap = metrics.snapshot()
        snap["canary_state"] = controller.get_state()
        return jsonify(snap)

    @app.route("/admin/status", methods=["GET"])
    def admin_status():
        return jsonify(controller.get_state())

    @app.route("/admin/canary/weight", methods=["POST"])
    def set_canary_weight():
        data = request.get_json(silent=True) or {}
        weight = data.get("weight")
        try:
            controller.set_canary_weight(float(weight))
            return jsonify({"ok": True, "canary_state": controller.get_state()})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.route("/admin/canary/set", methods=["POST"])
    def set_canary_version():
        data = request.get_json(silent=True) or {}
        version = data.get("version")
        weight = data.get("weight")
        if version not in models:
            return jsonify({"ok": False, "error": f"Unknown version: {version}"}), 400
        try:
            controller.set_canary_version(version)
            if weight is not None:
                controller.set_canary_weight(float(weight))
            return jsonify({"ok": True, "canary_state": controller.get_state()})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.route("/admin/canary/promote", methods=["POST"])
    def promote_canary():
        try:
            controller.promote_canary()
            return jsonify({"ok": True, "canary_state": controller.get_state()})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.route("/admin/canary/rollback", methods=["POST"])
    def rollback_canary():
        try:
            controller.rollback_canary(reason="manual")
            return jsonify({"ok": True, "canary_state": controller.get_state()})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.route("/admin/thresholds", methods=["POST"])
    def set_thresholds():
        data = request.get_json(silent=True) or {}
        try:
            controller.set_thresholds(data)
            return jsonify({"ok": True, "thresholds": controller.get_state().get("thresholds")})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.route("/admin/canary/toggle_auto", methods=["POST"])
    def toggle_auto():
        data = request.get_json(silent=True) or {}
        enabled = bool(data.get("enabled", True))
        controller.toggle_auto(enabled)
        return jsonify({"ok": True, "auto_canary_enabled": controller.get_state().get("auto_canary_enabled")})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), threaded=True)



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/canary/config', methods=['GET', 'POST'])
def _auto_stub_canary_config():
    return 'Auto-generated stub for /canary/config', 200


@app.route('/reset', methods=['POST'])
def _auto_stub_reset():
    return 'Auto-generated stub for /reset', 200
