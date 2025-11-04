import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify(
        status="ok",
        message=os.getenv("APP_MESSAGE", "Hello from Oracle VM"),
        env=os.getenv("FLASK_ENV", "production"),
    )

@app.route("/healthz")
def healthz():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

