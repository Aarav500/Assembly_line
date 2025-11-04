import os
from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)

    # Load config
    app.config.from_object("app.config.Config")

    # Register blueprints/routes
    from app.routes import bp as routes_bp
    app.register_blueprint(routes_bp)

    # Ensure policy directory exists
    policy_dir = app.config.get("POLICY_DIR", "policies")
    if not os.path.isdir(policy_dir):
        os.makedirs(policy_dir, exist_ok=True)

    return app

