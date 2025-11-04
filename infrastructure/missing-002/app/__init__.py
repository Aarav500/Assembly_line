import os
from flask import Flask, jsonify
from .config import Config
from .extensions import db, migrate, login_manager, mail
from .extensions import cors as cors_ext
from .models import User
from .auth.routes import auth_bp
from .users.routes import admin_bp
from .account.routes import account_bp
from .cli import register_cli


def create_app(config_object: type | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object or Config())

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    cors_ext.init_app(app, resources={r"/*": {"origins": app.config.get("ALLOWED_ORIGINS", "*")}})

    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(account_bp, url_prefix="/account")

    # Health endpoint
    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    register_cli(app)

    return app

