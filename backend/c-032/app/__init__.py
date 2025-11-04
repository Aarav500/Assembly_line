import os
from flask import Flask
from .config import Config
from .logging_setup import setup_logging
from .routes import api_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config())

    setup_logging(app)

    app.register_blueprint(api_bp, url_prefix="/api/v1")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app

