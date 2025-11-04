import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import os
from flask import Flask, jsonify
from dotenv import load_dotenv

from config import get_config
from payments.stripe_handlers import stripe_bp
from payments.paypal_handlers import paypal_bp


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__)
    app.config.from_object(get_config())

    # Logging setup
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    # Blueprints
    app.register_blueprint(stripe_bp)
    app.register_blueprint(paypal_bp)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad_request", "message": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not_found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "server_error", "message": "An unexpected error occurred"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", 5000)))



@app.route('/stripe/create-payment-intent', methods=['POST'])
def _auto_stub_stripe_create_payment_intent():
    return 'Auto-generated stub for /stripe/create-payment-intent', 200


@app.route('/paypal/create-order', methods=['POST'])
def _auto_stub_paypal_create_order():
    return 'Auto-generated stub for /paypal/create-order', 200
