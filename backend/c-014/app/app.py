from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify(
        message="Hello from Flask!",
        environment=os.getenv("FLASK_ENV", "production")
    )

@app.route("/healthz")
def healthz():
    return jsonify(status="ok")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_ENV") == "development",
    )

