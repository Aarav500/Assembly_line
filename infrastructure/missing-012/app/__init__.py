from flask import Flask
from .config import Config
from .extensions import db
from .routes.preferences import bp as preferences_bp
from .routes.events import bp as events_bp
from .routes.digest import bp as digest_bp
from .cli import register_cli


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object or Config())

    db.init_app(app)

    with app.app_context():
        # Create tables if they don't exist
        db.create_all()

    # Blueprints
    app.register_blueprint(preferences_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(digest_bp)

    # CLI
    register_cli(app)

    return app

