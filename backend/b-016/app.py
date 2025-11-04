import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from generators.persona_generator import generate_personas
from generators.journey_generator import generate_journeys
import os

app = Flask(__name__)


def parse_int(value, default):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


@app.route("/", methods=["GET"]) 
def root():
    return jsonify({
        "service": "generate-user-personas-and-realistic-user-journeys",
        "version": "1.0.0",
        "endpoints": [
            {"method": "POST", "path": "/api/generate", "description": "Generate user personas and realistic user journeys"}
        ]
    })


@app.route("/api/generate", methods=["POST"]) 
def generate():
    try:
        data = request.get_json(force=True, silent=True) or {}
        product = data.get("product", "A digital product")
        industry = data.get("industry", "General")
        audience = data.get("audience", [])
        if isinstance(audience, str):
            audience = [audience]
        personas_count = parse_int(data.get("personas"), 3)
        journeys_per_persona = parse_int(data.get("journeys_per_persona"), 1)
        scenario = data.get("journey_scenario", "Discover, onboard, and start using the product")
        stages = data.get("stages") or [
            "Awareness",
            "Consideration",
            "Onboarding",
            "Activation",
            "Retention"
        ]
        locale = data.get("locale", "en-US")
        seed = data.get("seed")
        try:
            seed = int(seed) if seed is not None else None
        except Exception:
            seed = None

        personas = generate_personas(
            n=personas_count,
            product=product,
            industry=industry,
            audience=audience,
            locale=locale,
            seed=seed
        )

        journeys = generate_journeys(
            personas=personas,
            scenario=scenario,
            stages=stages,
            journeys_per_persona=journeys_per_persona,
            product=product,
            industry=industry,
            seed=seed
        )

        return jsonify({
            "input": {
                "product": product,
                "industry": industry,
                "audience": audience,
                "personas": personas_count,
                "journeys_per_persona": journeys_per_persona,
                "journey_scenario": scenario,
                "stages": stages,
                "locale": locale,
                "seed": seed
            },
            "personas": personas,
            "journeys": journeys
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/personas', methods=['GET'])
def _auto_stub_personas():
    return 'Auto-generated stub for /personas', 200


@app.route('/api/journey/1', methods=['GET'])
def _auto_stub_api_journey_1():
    return 'Auto-generated stub for /api/journey/1', 200


@app.route('/api/journey/999', methods=['GET'])
def _auto_stub_api_journey_999():
    return 'Auto-generated stub for /api/journey/999', 200
