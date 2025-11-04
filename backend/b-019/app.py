import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify

from matcher import match_startup, preprocess_opportunities

DATA_PATH = os.environ.get("DATA_PATH", os.path.join(os.path.dirname(__file__), "data", "opportunities.json"))


def load_opportunities(path: str):
    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f)
    return items


def create_app():
    app = Flask(__name__)

    # Load and preprocess opportunities at startup
    raw_opps = load_opportunities(DATA_PATH)
    app.config["OPPORTUNITIES_RAW"] = raw_opps
    app.config["OPPORTUNITIES"] = preprocess_opportunities(raw_opps)

    @app.route("/health", methods=["GET"]) 
    def health():
        return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"})

    @app.route("/api/opportunities", methods=["GET"]) 
    def list_opportunities():
        return jsonify(app.config["OPPORTUNITIES_RAW"])

    @app.route("/api/match", methods=["POST"]) 
    def match():
        try:
            payload = request.get_json(force=True, silent=False)
        except Exception:
            return jsonify({"error": "Invalid or missing JSON body"}), 400

        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object"}), 400

        profile = payload
        results = match_startup(profile, app.config["OPPORTUNITIES"]) 
        return jsonify(results)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)



@app.route('/sources/investor', methods=['GET'])
def _auto_stub_sources_investor():
    return 'Auto-generated stub for /sources/investor', 200
