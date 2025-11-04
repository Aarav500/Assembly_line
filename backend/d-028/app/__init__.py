import logging
from flask import Flask
from .config import Config
from .routes import webhook_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config())

    # Logging
    logging.basicConfig(level=getattr(logging, app.config.get("LOG_LEVEL", "INFO")))

    app.register_blueprint(webhook_bp, url_prefix="/webhook")

    @app.route("/healthz", methods=["GET"])  # Simple health check
    def healthz():
        return {"status": "ok"}, 200

    return app

