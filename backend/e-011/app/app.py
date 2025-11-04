from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({"status": "ok", "app": "flask", "message": "Hello from Flask over HTTPS!"})

@app.route("/healthz")
def healthz():
    return "ok", 200

@app.route("/readyz")
def readyz():
    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
