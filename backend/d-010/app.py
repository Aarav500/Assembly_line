import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import os
import threading
import time
from flask import Flask, request, jsonify

from orchestrator import CanaryOrchestrator
from providers.fake import FakeRouter

app = Flask(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("canary-orchestrator")

router = FakeRouter()
orchestrator = CanaryOrchestrator(router=router)


def _background_evaluator():
    interval = 1.0
    logger.info("Background evaluator started with tick %.1fs", interval)
    while True:
        try:
            orchestrator.tick()
        except Exception as e:
            logger.exception("Evaluator error: %s", e)
        time.sleep(interval)


def _start_background_thread():
    t = threading.Thread(target=_background_evaluator, name="canary-evaluator", daemon=True)
    t.start()


@app.route("/health", methods=["GET"])  # liveness/readiness
def health():
    return jsonify({"status": "ok"})


@app.route("/deployments", methods=["POST"])  # create a canary deployment
def create_deployment():
    data = request.get_json(force=True, silent=False)
    try:
        dep = orchestrator.create_deployment(data)
        return jsonify(dep.to_dict()), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("create_deployment failed")
        return jsonify({"error": "internal_error", "detail": str(e)}), 500


@app.route("/deployments", methods=["GET"])  # list
def list_deployments():
    deps = orchestrator.list_deployments()
    return jsonify([d.to_dict(summary=True) for d in deps])


@app.route("/deployments/<dep_id>", methods=["GET"])  # get status
def get_deployment(dep_id):
    dep = orchestrator.get(dep_id)
    if not dep:
        return jsonify({"error": "not_found"}), 404
    return jsonify(dep.to_dict())


@app.route("/deployments/<dep_id>/cancel", methods=["POST"])  # cancel/rollback
def cancel_deployment(dep_id):
    try:
        dep = orchestrator.cancel(dep_id)
        if dep is None:
            return jsonify({"error": "not_found"}), 404
        return jsonify(dep.to_dict())
    except Exception as e:
        logger.exception("cancel failed")
        return jsonify({"error": "internal_error", "detail": str(e)}), 500


@app.route("/metrics", methods=["POST"])  # ingest metrics samples
def ingest_metrics():
    data = request.get_json(force=True, silent=False)
    dep_id = data.get("deployment_id")
    if not dep_id:
        return jsonify({"error": "deployment_id is required"}), 400
    metrics = data.get("metrics") or {}
    ts = data.get("timestamp")
    try:
        orchestrator.add_metrics(dep_id, metrics, ts)
        return jsonify({"status": "accepted"}), 202
    except KeyError:
        return jsonify({"error": "not_found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("ingest_metrics failed")
        return jsonify({"error": "internal_error", "detail": str(e)}), 500


if __name__ == "__main__":
    _start_background_thread()
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/traffic', methods=['POST'])
def _auto_stub_traffic():
    return 'Auto-generated stub for /traffic', 200
