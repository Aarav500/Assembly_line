import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from flask import Flask, request, jsonify

from core.engine import suggest

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/suggest")
def suggest_endpoint():
    try:
        payload = request.get_json(force=True, silent=False)
    except Exception as e:
        return jsonify({"error": f"Invalid JSON: {e}"}), 400

    try:
        result = suggest(payload or {})
        return jsonify(result)
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": f"Server error: {e}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)



def create_app():
    return app
