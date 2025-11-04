import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
from flasgger import Swagger
import uuid

app = Flask(__name__)

# Basic Swagger template
swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Example Flask API",
        "description": "Auto-generated API documentation with Flasgger + MkDocs",
        "version": "1.0.0",
    },
    "basePath": "/",
    "schemes": ["http", "https"],
    "consumes": ["application/json"],
    "produces": ["application/json"],
    "securityDefinitions": {},
    "definitions": {
        "Item": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "example": "a1b2c3"},
                "name": {"type": "string", "example": "Sample Item"},
                "description": {"type": "string", "example": "Optional details"}
            },
            "required": ["name"]
        },
        "ItemCreateRequest": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"}
            },
            "required": ["name"]
        }
    },
}

swagger = Swagger(app, template=swagger_template)

ITEMS = {}


@app.route("/health", methods=["GET"])
def health():
    """
    Health check endpoint
    ---
    tags:
      - Health
    responses:
      200:
        description: Service status
        schema:
          type: object
          properties:
            status:
              type: string
              example: ok
    """
    return jsonify({"status": "ok"})


@app.route("/items", methods=["GET"])
def list_items():
    """
    List all items
    ---
    tags:
      - Items
    responses:
      200:
        description: A list of items
        schema:
          type: array
          items:
            $ref: '#/definitions/Item'
    """
    return jsonify(list(ITEMS.values()))


@app.route("/items", methods=["POST"])
def create_item():
    """
    Create a new item
    ---
    tags:
      - Items
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/ItemCreateRequest'
    responses:
      201:
        description: Item created successfully
        schema:
          $ref: '#/definitions/Item'
      400:
        description: Invalid input
    """
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "'name' is required"}), 400
    item_id = uuid.uuid4().hex[:8]
    item = {
        "id": item_id,
        "name": name,
        "description": data.get("description", "")
    }
    ITEMS[item_id] = item
    return jsonify(item), 201


@app.route("/items/<item_id>", methods=["GET"])
def get_item(item_id):
    """
    Get an item by ID
    ---
    tags:
      - Items
    parameters:
      - in: path
        name: item_id
        type: string
        required: true
        description: The ID of the item
    responses:
      200:
        description: The requested item
        schema:
          $ref: '#/definitions/Item'
      404:
        description: Item not found
    """
    item = ITEMS.get(item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    return jsonify(item)


@app.route("/items/<item_id>", methods=["DELETE"])
def delete_item(item_id):
    """
    Delete an item by ID
    ---
    tags:
      - Items
    parameters:
      - in: path
        name: item_id
        type: string
        required: true
        description: The ID of the item
    responses:
      204:
        description: Item deleted successfully
      404:
        description: Item not found
    """
    if item_id not in ITEMS:
        return jsonify({"error": "Not found"}), 404
    del ITEMS[item_id]
    return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app


@app.route('/api/health', methods=['GET'])
def _auto_stub_api_health():
    return 'Auto-generated stub for /api/health', 200


@app.route('/api/users', methods=['GET'])
def _auto_stub_api_users():
    return 'Auto-generated stub for /api/users', 200
