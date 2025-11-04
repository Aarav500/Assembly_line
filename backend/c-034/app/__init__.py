import logging
from flask import Flask
from .config import Config
from .routes import bp as routes_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Logging setup
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app.register_blueprint(routes_bp)
    return app

