import os
import time
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/")
def root():
    return jsonify({"message": "Flask app is running", "endpoints": ["/health", "/items", "/echo"]})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/items")
def items():
    try:
        count = int(request.args.get("count", 50))
        count = max(0, min(count, 1000))
    except ValueError:
        count = 50

    try:
        delay_ms = int(request.args.get("delay_ms", 0))
        delay_ms = max(0, min(delay_ms, 5000))
    except ValueError:
        delay_ms = 0

    if delay_ms:
        time.sleep(delay_ms / 1000.0)

    data = [{"id": i, "value": f"item-{i}"} for i in range(count)]
    return jsonify({"count": count, "delay_ms": delay_ms, "items": data})


@app.route("/echo", methods=["POST"])
def echo():
    payload = request.get_json(silent=True) or {}
    return jsonify({"echo": payload, "received": True})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "0.0.0.0")
    app.run(host=host, port=port) 

