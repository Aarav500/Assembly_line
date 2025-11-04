import os
from flask import Flask, jsonify

app = Flask(__name__)

APP_MESSAGE = os.environ.get("APP_MESSAGE", "Hello from GitOps demo")
VERSION = os.environ.get("VERSION", "0.1.0")

@app.route("/")
def index():
    return jsonify({
        "message": APP_MESSAGE,
        "version": VERSION,
        "service": "gitops-demo"
    })

@app.route("/healthz")
def healthz():
    return "ok", 200

@app.route("/version")
def version():
    return jsonify({"version": VERSION})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)

