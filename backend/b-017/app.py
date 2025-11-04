import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
from flask import Flask, jsonify, request, Response

app = Flask(__name__)

SERVICE_NAME = "acceptance-criteria-and-test-scenarios-baked-into-manifest"
SERVICE_VERSION = "1.0.0"

# In-memory store
DB = {
    "items": [],
    "next_id": 1,
}


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@app.route("/")
def root():
    return jsonify({
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "endpoints": [
            "/health", "/items", "/items/<id>", "/__manifest"
        ]
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION
    })


@app.route("/__manifest")
def manifest():
    # Serve the manifest file for transparency
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yml")
    if not os.path.exists(manifest_path):
        return jsonify({"error": "manifest.yml not found"}), 404
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = f.read()
    return Response(data, mimetype="text/yaml")


@app.route("/items", methods=["GET"]) 
def list_items():
    return jsonify(DB["items"])


@app.route("/items", methods=["POST"]) 
def create_item():
    if not request.is_json:
        return jsonify({"error": "Expected application/json body"}), 400
    payload = request.get_json(silent=True) or {}

    name = payload.get("name")
    price = payload.get("price")

    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "Field 'name' is required and must be a non-empty string"}), 400
    if not (isinstance(price, int) or isinstance(price, float)):
        return jsonify({"error": "Field 'price' is required and must be a number"}), 400
    if price < 0:
        return jsonify({"error": "Field 'price' must be non-negative"}), 400

    item = {
        "id": DB["next_id"],
        "name": name.strip(),
        "price": float(price),
        "created_at": now_iso(),
    }
    DB["next_id"] += 1
    DB["items"].append(item)

    return jsonify(item), 201


@app.route("/items/<int:item_id>", methods=["GET"]) 
def get_item(item_id: int):
    for item in DB["items"]:
        if item["id"] == item_id:
            return jsonify(item)
    return jsonify({"error": "Item not found"}), 404


@app.route("/items/<int:item_id>", methods=["DELETE"]) 
def delete_item(item_id: int):
    for idx, item in enumerate(DB["items"]):
        if item["id"] == item_id:
            del DB["items"][idx]
            return ("", 204)
    return jsonify({"error": "Item not found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))



def create_app():
    return app


@app.route('/echo', methods=['POST'])
def _auto_stub_echo():
    return 'Auto-generated stub for /echo', 200
