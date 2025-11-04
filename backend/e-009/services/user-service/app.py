from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route("/healthz")
def healthz():
    return jsonify(status="ok", service=os.getenv("SERVICE_NAME", "user-service"))

@app.route("/users")
def users():
    return jsonify(users=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}])

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

