import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import logging
from flask import Flask, jsonify, request
from autoscaler import AutoScaler
from config import ConfigLoader, ConfigError

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


def create_app():
    app = Flask(__name__)

    # Load config
    config_path = os.getenv("CONFIG_PATH", "config/policies.yaml")
    try:
        loader = ConfigLoader()
        cfg = loader.load(config_path)
    except ConfigError as e:
        logger.error(f"Failed to load config: {e}")
        cfg = loader.default_config()
        logger.warning("Using default config")

    # Init autoscaler
    reconcile_seconds = int(os.getenv("RECONCILE_SECONDS", "30"))
    autoscaler = AutoScaler(cfg, interval_seconds=reconcile_seconds)
    autoscaler.start()

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    @app.route("/status", methods=["GET"])
    def status():
        return jsonify(autoscaler.get_status())

    @app.route("/config", methods=["GET"])
    def get_config():
        return jsonify(autoscaler.get_config().model_dump())

    @app.route("/config", methods=["PUT"])
    def update_config():
        try:
            body = request.get_json(force=True)
            loader = ConfigLoader()
            cfg = loader.from_dict(body)
            autoscaler.update_config(cfg)
            return jsonify({"ok": True}), 200
        except Exception as e:
            logger.exception("Failed to update config")
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.route("/reconcile", methods=["POST"])
    def reconcile():
        autoscaler.reconcile_once()
        return jsonify({"ok": True})

    @app.route("/scale/now", methods=["POST"])
    def scale_now():
        body = request.get_json(force=True)
        policy = body.get("policy")
        target = body.get("target_gpus")
        if policy is None or target is None:
            return jsonify({"ok": False, "error": "policy and target_gpus required"}), 400
        try:
            autoscaler.scale_now(policy, int(target))
            return jsonify({"ok": True})
        except Exception as e:
            logger.exception("Manual scale failed")
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.route("/metrics", methods=["GET"])  # simple JSON metrics endpoint
    def metrics():
        return jsonify(autoscaler.get_metrics_snapshot())

    # Embed autoscaler instance for external access/testing
    app.autoscaler = autoscaler
    return app


if __name__ == "__main__":
    app = create_app()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    app.run(host=host, port=port)



@app.route('/pools', methods=['GET'])
def _auto_stub_pools():
    return 'Auto-generated stub for /pools', 200


@app.route('/pools/pool-1/jobs', methods=['POST'])
def _auto_stub_pools_pool_1_jobs():
    return 'Auto-generated stub for /pools/pool-1/jobs', 200


@app.route('/pools/pool-1/scale', methods=['POST'])
def _auto_stub_pools_pool_1_scale():
    return 'Auto-generated stub for /pools/pool-1/scale', 200
