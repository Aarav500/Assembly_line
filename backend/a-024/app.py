import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify
from pricing import PricingCatalog
from estimators import compute_forecast


def create_app():
    app = Flask(__name__)

    pricing_file = os.environ.get("PRICING_FILE", os.path.join(os.path.dirname(__file__), "models.json"))
    catalog = PricingCatalog.from_json(pricing_file)

    @app.route("/health", methods=["GET"]) 
    def health():
        return jsonify({"status": "ok"})

    @app.route("/models", methods=["GET"]) 
    def models():
        return jsonify({
            "models": [m.to_dict() for m in catalog.all_models()],
            "count": len(catalog)
        })

    @app.route("/forecast", methods=["POST"]) 
    def forecast():
        try:
            payload = request.get_json(silent=True) or {}
            result = compute_forecast(catalog, payload)
            return jsonify(result)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except KeyError as e:
            return jsonify({"error": f"Missing required field: {e}"}), 400
        except Exception as e:
            return jsonify({"error": "Internal server error", "detail": str(e)}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

