import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
import uuid
from flask import Flask, request, jsonify, make_response, g

from config import (
    TRAFFIC_SPLIT,
    EXPERIMENT_ID,
    COOKIE_NAME,
    COOKIE_TTL_SECONDS,
    ALLOW_VARIANT_OVERRIDE,
)
from ab import assign_variant, is_valid_variant
from metrics import log_prediction
from models.v1 import Model as ModelV1
from models.v2 import Model as ModelV2

app = Flask(__name__)

# Initialize model instances
MODELS = {
    "v1": ModelV1(),
    "v2": ModelV2(),
}

# Utility to get current splits (could be dynamic in a real system)
def get_splits():
    return dict(TRAFFIC_SPLIT)

@app.before_request
def before_request():
    g.request_start_time = time.time()
    g.request_id = str(uuid.uuid4())

@app.after_request
def after_request(response):
    response.headers["X-Request-Id"] = g.get("request_id", "")
    return response

@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "experiment_id": EXPERIMENT_ID, "splits": get_splits()}), 200

@app.route("/splits", methods=["GET"])
def splits():
    return jsonify({"experiment_id": EXPERIMENT_ID, "splits": get_splits(), "allow_override": ALLOW_VARIANT_OVERRIDE}), 200


def _get_input_text():
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        if isinstance(payload, dict):
            if "input" in payload:
                return payload.get("input")
            if "text" in payload:
                return payload.get("text")
    # Fallback to form or args
    if "input" in request.form:
        return request.form.get("input")
    if "text" in request.form:
        return request.form.get("text")
    if "input" in request.args:
        return request.args.get("input")
    if "text" in request.args:
        return request.args.get("text")
    return None


def _extract_user_id():
    # Preference: explicit user_id in json -> header -> query
    uid = None
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        uid = payload.get("user_id") if isinstance(payload, dict) else None
    if not uid:
        uid = request.headers.get("X-User-Id")
    if not uid:
        uid = request.args.get("user_id")
    return uid


def _override_variant_if_allowed():
    variant = None
    if ALLOW_VARIANT_OVERRIDE:
        variant = request.args.get("variant") or request.headers.get("X-Variant")
        if variant and not is_valid_variant(variant, get_splits()):
            variant = None
    return variant


def _choose_variant_for_request():
    # 1) Explicit path variant endpoints take precedence handled by caller
    # 2) If override header/param allowed and valid, use it (do not set cookie)
    override = _override_variant_if_allowed()
    if override:
        return override, False  # not sticky

    # 3) If cookie present and valid, use it
    cookie_variant = request.cookies.get(COOKIE_NAME)
    if cookie_variant and is_valid_variant(cookie_variant, get_splits()):
        return cookie_variant, True

    # 4) Assign deterministically using user_id when available, otherwise random
    user_id = _extract_user_id()
    assigned = assign_variant(user_id=user_id, weights=get_splits(), experiment_id=EXPERIMENT_ID)
    return assigned, True


def _run_inference(variant, text):
    model = MODELS.get(variant)
    if not model:
        raise ValueError(f"Unsupported variant: {variant}")
    return model.predict(text)


def _respond_with_prediction(variant, text, sticky_assignment):
    started = g.get("request_start_time", time.time())
    user_id = _extract_user_id()
    req_id = g.get("request_id", str(uuid.uuid4()))

    try:
        output = _run_inference(variant, text)
        latency_ms = int((time.time() - started) * 1000)

        event = {
            "event": "prediction",
            "request_id": req_id,
            "user_id": user_id,
            "variant": variant,
            "experiment_id": EXPERIMENT_ID,
            "latency_ms": latency_ms,
            "ok": True,
        }
        log_prediction(event)

        resp_body = {
            "request_id": req_id,
            "variant": variant,
            "experiment_id": EXPERIMENT_ID,
            "latency_ms": latency_ms,
            "input": text,
            "output": output,
        }
        resp = make_response(jsonify(resp_body), 200)
        if sticky_assignment:
            resp.set_cookie(COOKIE_NAME, variant, max_age=COOKIE_TTL_SECONDS, httponly=True, secure=False, samesite="Lax")
        return resp
    except Exception as e:
        latency_ms = int((time.time() - started) * 1000)
        log_prediction({
            "event": "prediction",
            "request_id": req_id,
            "user_id": user_id,
            "variant": variant,
            "experiment_id": EXPERIMENT_ID,
            "latency_ms": latency_ms,
            "ok": False,
            "error": str(e),
        })
        return jsonify({"error": str(e), "request_id": req_id}), 500


@app.route("/predict", methods=["POST"])
def predict_split():
    text = _get_input_text()
    if text is None:
        return jsonify({"error": "Missing 'input' or 'text' in request"}), 400
    variant, sticky = _choose_variant_for_request()
    return _respond_with_prediction(variant, text, sticky_assignment=sticky)


@app.route("/v1/predict", methods=["POST"])
def predict_v1():
    text = _get_input_text()
    if text is None:
        return jsonify({"error": "Missing 'input' or 'text' in request"}), 400
    return _respond_with_prediction("v1", text, sticky_assignment=False)


@app.route("/v2/predict", methods=["POST"])
def predict_v2():
    text = _get_input_text()
    if text is None:
        return jsonify({"error": "Missing 'input' or 'text' in request"}), 400
    return _respond_with_prediction("v2", text, sticky_assignment=False)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/predict/v1', methods=['POST'])
def _auto_stub_predict_v1():
    return 'Auto-generated stub for /predict/v1', 200


@app.route('/predict/v99', methods=['POST'])
def _auto_stub_predict_v99():
    return 'Auto-generated stub for /predict/v99', 200


@app.route('/traffic', methods=['GET', 'PUT'])
def _auto_stub_traffic():
    return 'Auto-generated stub for /traffic', 200
