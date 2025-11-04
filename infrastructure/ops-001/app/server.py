import os
from flask import Flask, jsonify

app = Flask(__name__)
COLOR = os.getenv("COLOR", "unknown")
RELEASE = os.getenv("RELEASE", "dev")

@app.get("/")
def index():
    return jsonify(status="ok", color=COLOR, release=RELEASE), 200

@app.get("/healthz")
def healthz():
    return "ok", 200

@app.get("/livez")
def livez():
    return "alive", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

