import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
import logging
from flask import Flask, request, jsonify, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from metrics import (
    INFERENCE_REQUESTS,
    INFERENCE_LATENCY,
    TOKENS_PROCESSED,
    HALLUCINATION_SCORE,
    HALLUCINATION_EVENTS,
    APP_INFO,
)
from hallucination import compute_hallucination_score, is_hallucination
from model import generate
from utils import simple_tokenize


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("monitoring-app")

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/metrics", methods=["GET"])
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route("/infer", methods=["POST"])
def infer():
    endpoint = "/infer"
    start = time.perf_counter()
    try:
        payload = request.get_json(force=True, silent=False)
        if not payload or "prompt" not in payload or not isinstance(payload["prompt"], str):
            INFERENCE_REQUESTS.labels(endpoint=endpoint, status="bad_request").inc()
            return jsonify({"error": "Field 'prompt' (string) is required"}), 400

        prompt = payload["prompt"]
        references = payload.get("references")  # optional: string or list of strings
        # Simulate/perform model generation
        output = generate(prompt)

        # Token counts for throughput
        input_tokens = len(simple_tokenize(prompt))
        output_tokens = len(simple_tokenize(output))
        TOKENS_PROCESSED.labels(type="input").inc(input_tokens)
        TOKENS_PROCESSED.labels(type="output").inc(output_tokens)

        # Hallucination scoring (optional if references provided)
        halluc_score = None
        halluc_flag = None
        if references is not None:
            try:
                halluc_score = compute_hallucination_score(output, references)
                HALLUCINATION_SCORE.observe(halluc_score)
                halluc_flag = is_hallucination(halluc_score)
                if halluc_flag:
                    HALLUCINATION_EVENTS.labels(reason="low_similarity").inc()
            except Exception as e:
                logger.exception("Hallucination scoring failed: %s", e)
                HALLUCINATION_EVENTS.labels(reason="scoring_error").inc()

        # Latency
        latency = time.perf_counter() - start
        INFERENCE_LATENCY.labels(endpoint=endpoint).observe(latency)
        INFERENCE_REQUESTS.labels(endpoint=endpoint, status="success").inc()

        return jsonify({
            "output": output,
            "latency_ms": round(latency * 1000.0, 3),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "hallucination_score": halluc_score,
            "hallucination_flag": halluc_flag,
        })
    except Exception as e:
        logger.exception("Inference error: %s", e)
        INFERENCE_REQUESTS.labels(endpoint=endpoint, status="error").inc()
        latency = time.perf_counter() - start
        INFERENCE_LATENCY.labels(endpoint=endpoint).observe(latency)
        return jsonify({"error": "internal_error", "message": str(e)}), 500


if __name__ == "__main__":
    # Set app info metric for visibility
    APP_INFO.info({"version": os.getenv("APP_VERSION", "0.1.0"), "service": "model-monitor"})
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))



def create_app():
    return app


@app.route('/predict', methods=['POST'])
def _auto_stub_predict():
    return 'Auto-generated stub for /predict', 200
