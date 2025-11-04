import os
from flask import Flask
from .config import load_config
from .routes import register_routes


def create_app(region: str | None = None) -> Flask:
    app = Flask(__name__)
    cfg = load_config(region)
    app.config.update(cfg)

    register_routes(app)
    return app

