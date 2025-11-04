import os
import socket
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.get("/")
def root():
    return jsonify({
        "service": "blue",
        "version": "1.0.0",
        "hostname": socket.gethostname(),
        "path": request.path
    })

@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "blue"}), 200

@app.get("/slow")
def slow():
    # Simulate work via optional delay
    try:
        ms = int(request.args.get("ms", "0"))
    except Exception:
        ms = 0
    if ms > 0:
        import time
        time.sleep(ms / 1000.0)
    return jsonify({"service": "blue", "slow": ms})

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(host="0.0.0.0", port=port)

