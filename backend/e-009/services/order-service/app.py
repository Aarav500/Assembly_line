from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route("/healthz")
def healthz():
    return jsonify(status="ok", service=os.getenv("SERVICE_NAME", "order-service"))

@app.route("/orders")
def orders():
    return jsonify(orders=[{"id": 101, "item": "Widget", "qty": 2}, {"id": 102, "item": "Gadget", "qty": 1}])

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

