import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from generator.utils import parse_entities_spec
from generator.erd import generate_mermaid_erd, generate_dot_erd
from generator.openapi import generate_openapi

app = Flask(__name__)


@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})


@app.route("/", methods=["GET"]) 
def root():
    return jsonify({
        "message": "Auto-generate ERD and API contracts from idea entities",
        "endpoints": {
            "POST /generate": "Generate ERD (Mermaid + DOT) and OpenAPI from a entities spec"
        },
        "example": {
            "curl": "curl -X POST http://localhost:5000/generate -H 'Content-Type: application/json' -d @sample/entities.json"
        }
    })


@app.route("/generate", methods=["POST"]) 
def generate():
    try:
        spec = request.get_json(force=True, silent=False)
        if not isinstance(spec, dict):
            return jsonify({"error": "Invalid JSON: expected an object"}), 400
        entities = parse_entities_spec(spec)
        mermaid = generate_mermaid_erd(entities)
        dot = generate_dot_erd(entities)
        openapi = generate_openapi(entities, title=spec.get("title", "Idea Entities API"), version=spec.get("version", "1.0.0"), base_path=spec.get("basePath", "/api"))
        return jsonify({
            "erd": {
                "mermaid": mermaid,
                "dot": dot
            },
            "openapi": openapi
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app


@app.route('/api/generate-erd', methods=['POST'])
def _auto_stub_api_generate_erd():
    return 'Auto-generated stub for /api/generate-erd', 200


@app.route('/api/generate-contracts', methods=['POST'])
def _auto_stub_api_generate_contracts():
    return 'Auto-generated stub for /api/generate-contracts', 200
