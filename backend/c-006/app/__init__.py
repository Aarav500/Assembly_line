import os
from flask import Flask
from .config import Config
from .extensions import init_extensions
from .routes import register_routes
from .cli import register_cli


def create_app(config_object=None):
    app = Flask(__name__)

    # Load base config then optional override
    app.config.from_object(config_object or Config)

    # Allow DATABASE_URL env var to override
    if os.environ.get("DATABASE_URL"):
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]

    init_extensions(app)
    register_routes(app)
    register_cli(app)

    return app

