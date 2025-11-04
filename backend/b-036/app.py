import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import traceback
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from generators.plan_generator import generate_test_plan
from generators.survey_generator import generate_survey


def create_app():
    app = Flask(__name__)
    CORS(app)

    @app.route("/", methods=["GET"]) 
    def index():
        return jsonify({
            "name": "auto-generate-user-testing-plans-and-surveys",
            "version": "1.0.0",
            "endpoints": {
                "health": {"method": "GET", "path": "/health"},
                "generate_plan": {"method": "POST", "path": "/generate/plan"},
                "generate_survey": {"method": "POST", "path": "/generate/survey"},
                "generate_bundle": {"method": "POST", "path": "/generate/bundle"}
            }
        })

    @app.route("/health", methods=["GET"]) 
    def health():
        return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"})

    @app.route("/generate/plan", methods=["POST"]) 
    def generate_plan_endpoint():
        try:
            payload = request.get_json(force=True, silent=False) or {}
            result = generate_test_plan(payload)
            return jsonify(result), 200
        except Exception as e:
            return jsonify({
                "error": str(e),
                "trace": traceback.format_exc()
            }), 400

    @app.route("/generate/survey", methods=["POST"]) 
    def generate_survey_endpoint():
        try:
            payload = request.get_json(force=True, silent=False) or {}
            result = generate_survey(payload)
            return jsonify(result), 200
        except Exception as e:
            return jsonify({
                "error": str(e),
                "trace": traceback.format_exc()
            }), 400

    @app.route("/generate/bundle", methods=["POST"]) 
    def generate_bundle_endpoint():
        try:
            payload = request.get_json(force=True, silent=False) or {}
            plan = generate_test_plan(payload.get("plan", payload))
            survey = generate_survey(payload.get("survey", payload))
            return jsonify({
                "bundle_id": f"bundle_{plan['id']}",
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "plan": plan,
                "survey": survey
            }), 200
        except Exception as e:
            return jsonify({
                "error": str(e),
                "trace": traceback.format_exc()
            }), 400

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



@app.route('/generate/testing-plan', methods=['POST'])
def _auto_stub_generate_testing_plan():
    return 'Auto-generated stub for /generate/testing-plan', 200
