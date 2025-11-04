import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify, request

import perf_baseline as pb

app = Flask(__name__)


@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})


@app.route("/metrics", methods=["GET"]) 
def metrics():
    return jsonify(pb.get_baseline())


@app.route("/rebench", methods=["POST"]) 
def rebench():
    data = request.get_json(silent=True) or {}
    total_ms = data.get("total_ms")
    try:
        if total_ms is not None:
            total_ms = int(total_ms)
    except Exception:
        return jsonify({"error": "total_ms must be integer milliseconds"}), 400

    baseline = pb.rerun(total_ms=total_ms)
    return jsonify(baseline)


@app.route("/") 
def root():
    base = pb.get_baseline()
    return jsonify({
        "name": "performance-baseline-collector",
        "version": base.get("version"),
        "generated_at": base.get("generated_at"),
        "endpoints": ["/health", "/metrics", "/rebench"],
    })


if __name__ == "__main__":
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_RUN_PORT", "5000"))
    app.run(host=host, port=port)



def create_app():
    return app
