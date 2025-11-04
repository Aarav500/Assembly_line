import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest

from config import AppConfig, load_config
from utils.logging import configure_logging, get_logger
from routing import SecureRouter


config: AppConfig = load_config()
configure_logging(config.LOG_LEVEL)
logger = get_logger(__name__)

app = Flask(__name__)
router = SecureRouter(config)


@app.route("/healthz", methods=["GET"])  # liveness
def healthz():
    return jsonify({"status": "ok"})


@app.route("/readyz", methods=["GET"])  # readiness
def readyz():
    status = router.readiness()

    http_code = 200 if status["ok"] else 503
    return jsonify(status), http_code


@app.route("/v1/infer", methods=["POST"])  # main inference endpoint
def infer():
    try:
        body = request.get_json(force=True, silent=False)
    except BadRequest:
        return jsonify({"error": {"code": "bad_request", "message": "Invalid JSON"}}), 400

    if not isinstance(body, dict):
        return jsonify({"error": {"code": "bad_request", "message": "Body must be a JSON object"}}), 400

    model = body.get("model")
    if not model or not isinstance(model, str):
        return jsonify({"error": {"code": "bad_request", "message": "Missing or invalid 'model'"}}), 400

    payload = {
        "input": body.get("input"),
        "params": body.get("params", {}),
    }

    # Metadata/context that may influence routing
    context = {
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "user_agent": request.headers.get("User-Agent"),
        "trace_id": request.headers.get("X-Trace-Id"),
        "request_headers": {k: v for k, v in request.headers.items()},
    }

    try:
        route_decision = router.decide(model_name=model, context=context)
    except Exception as e:
        logger.exception("routing_decision_error", extra={"model": model})
        return jsonify({"error": {"code": "routing_error", "message": str(e)}}), 500

    if route_decision.target == "deny":
        return jsonify({
            "error": {
                "code": "policy_denied",
                "message": route_decision.reason or "Request denied by policy",
            }
        }), 403

    try:
        result = router.execute(route_decision, payload)
    except router.AttestationError as e:
        return jsonify({"error": {"code": "attestation_failed", "message": str(e)}}), 502
    except router.BackendError as e:
        return jsonify({"error": {"code": "backend_error", "message": str(e)}}), 502
    except Exception as e:
        logger.exception("execution_error")
        return jsonify({"error": {"code": "internal_error", "message": "Unexpected error"}}), 500

    response = jsonify({
        "route": route_decision.target,
        "model": model,
        "result": result,
    })
    response.headers["X-Route-Decision"] = route_decision.target
    return response, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))



def create_app():
    return app


@app.route('/models', methods=['GET'])
def _auto_stub_models():
    return 'Auto-generated stub for /models', 200


@app.route('/inference/public-model', methods=['POST'])
def _auto_stub_inference_public_model():
    return 'Auto-generated stub for /inference/public-model', 200


@app.route('/inference/confidential-model', methods=['POST'])
def _auto_stub_inference_confidential_model():
    return 'Auto-generated stub for /inference/confidential-model', 200


@app.route('/route-model', methods=['POST'])
def _auto_stub_route_model():
    return 'Auto-generated stub for /route-model', 200
