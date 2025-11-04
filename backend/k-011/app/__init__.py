import os
import logging
from flask import Flask
from .config import Config, ensure_data_dir
from .routes import api_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    ensure_data_dir(app.config["DATA_DIR"])  # ensure data dir exists

    # Logging config
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app.logger.info("Starting app with SANDBOX_DRY_RUN=%s, DATA_DIR=%s", app.config["SANDBOX_DRY_RUN"], app.config["DATA_DIR"]) 

    # Register blueprints
    app.register_blueprint(api_bp)

    @app.errorhandler(400)
    def bad_request(e):
        return {"error": "bad_request", "message": str(e)}, 400

    @app.errorhandler(404)
    def not_found(e):
        return {"error": "not_found", "message": str(e)}, 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled error: %s", e)
        return {"error": "server_error", "message": "Internal server error"}, 500

    return app

