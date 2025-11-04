import logging
import os
from flask import Flask
from .config_loader import load_and_validate_config
from .routes import bp as routes_bp


def create_app(env: str | None = None, config_dir: str | None = None) -> Flask:
    env = env or os.getenv("APP_ENV", "development")
    config_dir = config_dir or os.getenv("APP_CONFIG_DIR", os.path.join(os.getcwd(), "config"))

    cfg_model = load_and_validate_config(config_dir=config_dir, env=env)

    app = Flask(__name__)

    # Attach structured config
    app.config["APP_CONFIG_MODEL"] = cfg_model
    app.config["APP_CONFIG"] = cfg_model.model_dump()

    # Configure logging
    level_name = cfg_model.logging.level.upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    app.register_blueprint(routes_bp)
    return app

