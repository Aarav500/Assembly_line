import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .routes import api_bp
from .utils import ensure_instance_dir


db = SQLAlchemy()


def create_app() -> Flask:
    app = Flask(__name__)

    # Load configuration
    app.config.from_object('config.Config')

    # Ensure instance folder exists (for sqlite default path)
    ensure_instance_dir()

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    app.register_blueprint(api_bp, url_prefix='/api')

    # Create tables if not exist
    with app.app_context():
        from . import models  # noqa: F401
        db.create_all()

    return app

