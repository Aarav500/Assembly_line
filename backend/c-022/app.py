import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
import requests
from flask import Flask, jsonify
from observability import init_observability

app = Flask(__name__)

# Initialize observability hooks (metrics, tracing, logging) automatically
init_observability(app)

@app.route("/")
def index():
    return jsonify({"status": "ok"})

@app.route("/hello")
def hello():
    # Example outbound call to demonstrate distributed tracing propagation
    # This will be traced automatically if OTEL tracing is enabled
    try:
        requests.get("https://httpbin.org/status/200", timeout=2)
    except Exception:
        pass
    return jsonify({"message": "hello"})

@app.route("/work")
def work():
    # Simulate work so you can see histograms/durations
    time.sleep(0.123)
    return jsonify({"work": "done"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/api/users/123', methods=['GET'])
def _auto_stub_api_users_123():
    return 'Auto-generated stub for /api/users/123', 200


@app.route('/metrics', methods=['GET'])
def _auto_stub_metrics():
    return 'Auto-generated stub for /metrics', 200
