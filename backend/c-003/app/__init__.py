import os
import logging
from flask import Flask, jsonify
from dotenv import load_dotenv

from .config import get_config
from .extensions import register_extensions
from .routes import register_blueprints


def create_app(config_name: str | None = None) -> Flask:
    # Load environment variables from .env if present
    load_dotenv(override=False)

    app = Flask(__name__)

    # Load configuration
    cfg = get_config(config_name)
    app.config.from_object(cfg)

    # Setup extensions (CORS, logging, etc.)
    register_extensions(app)

    # Register blueprints/routes
    register_blueprints(app)

    # Error handlers
    @app.errorhandler(404)
    def not_found(_e):
        return jsonify(error="Not Found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify(error="Method Not Allowed"), 405

    @app.errorhandler(500)
    def server_error(_e):
        app.logger.exception("Unhandled error")
        return jsonify(error="Internal Server Error"), 500

    # Root route for convenience
    @app.get("/")
    def index():
        return jsonify(app="flask-template", version=os.getenv("APP_VERSION", "1.0.0"))

    # Log startup configuration summary
    app.logger.info(
        "Flask app initialized: env=%s debug=%s host=%s port=%s",
        os.getenv("FLASK_ENV", "production"),
        app.config.get("DEBUG"),
        app.config.get("HOST"),
        app.config.get("PORT"),
    )

    return app

