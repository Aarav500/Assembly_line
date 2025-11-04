import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify
from data_generator import DataGenerator
from schema_store import SchemaStore

app = Flask(__name__)

SCHEMAS_PATH = os.environ.get("SCHEMAS_PATH", os.path.join(os.path.dirname(__file__), "data", "schemas.json"))
schema_store = SchemaStore(SCHEMAS_PATH)

@app.route("/health", methods=["GET"])  # simple health check
def health():
    return jsonify({"status": "ok"})

@app.route("/schemas", methods=["GET"])  # list schema names
def list_schemas():
    return jsonify({"schemas": schema_store.list_names()})

@app.route("/schemas", methods=["POST"])  # save schema by name
def save_schema():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    schema = payload.get("schema")
    if not name or not isinstance(name, str):
        return jsonify({"error": "name is required and must be a string"}), 400
    if not schema or not isinstance(schema, dict):
        return jsonify({"error": "schema is required and must be an object"}), 400
    schema_store.save(name, schema)
    return jsonify({"message": "saved", "name": name})

@app.route("/schemas/<name>", methods=["GET"])  # get schema by name
def get_schema(name):
    schema = schema_store.get(name)
    if schema is None:
        return jsonify({"error": f"schema '{name}' not found"}), 404
    return jsonify({"name": name, "schema": schema})

@app.route("/schemas/<name>", methods=["DELETE"])  # delete schema by name
def delete_schema(name):
    ok = schema_store.delete(name)
    if not ok:
        return jsonify({"error": f"schema '{name}' not found"}), 404
    return jsonify({"message": "deleted", "name": name})

@app.route("/generate", methods=["POST"])  # generate data
def generate_data():
    payload = request.get_json(silent=True) or {}

    # schema sourcing: inline or by name
    inline_schema = payload.get("schema")
    schema_name = payload.get("schema_name")
    count = payload.get("count")
    seed = payload.get("seed")
    locale = payload.get("locale")  # can be string or list

    if inline_schema is None and not schema_name:
        return jsonify({"error": "Provide either 'schema' or 'schema_name'"}), 400

    if inline_schema is not None and not isinstance(inline_schema, dict):
        return jsonify({"error": "'schema' must be an object"}), 400

    if schema_name:
        saved = schema_store.get(schema_name)
        if saved is None:
            return jsonify({"error": f"schema '{schema_name}' not found"}), 404
        schema = saved
    else:
        schema = inline_schema

    if count is not None:
        try:
            count = int(count)
            if count < 1:
                raise ValueError
        except Exception:
            return jsonify({"error": "'count' must be a positive integer"}), 400

    try:
        generator = DataGenerator(seed=seed, locale=locale)
        result = generator.generate(schema, count=count)
        return jsonify({
            "count": len(result),
            "data": result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app
