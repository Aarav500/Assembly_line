import logging
from flask import Flask
from .config import Config
from .extensions import db, oauth, register_oauth_clients


def create_app(config_object: type | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    # Initialize extensions
    db.init_app(app)
    oauth.init_app(app)
    register_oauth_clients(app)

    # Register blueprints
    from .auth.routes import auth_bp
    from .blueprints.protected import protected_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(protected_bp, url_prefix="/api")

    # Create DB and seed optionally
    with app.app_context():
        if app.config.get("AUTO_CREATE_DB", True):
            db.create_all()
        if app.config.get("SEED_DB", True):
            try:
                from .seed import seed_data
                seed_data(app)
            except Exception as e:
                logging.getLogger(__name__).warning("Seeding failed: %s", e)

    return app

