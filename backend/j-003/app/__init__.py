import os
from flask import Flask

__all__ = ["create_app"]
__version__ = "0.1.0"


def create_app() -> Flask:
    app = Flask(__name__)

    # Basic configuration
    app.config.from_mapping(
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "dev-secret-key"),
        JSONIFY_PRETTYPRINT_REGULAR=False,
        ENV=os.getenv("FLASK_ENV", "development"),
        DEBUG=os.getenv("FLASK_DEBUG", "1") == "1",
        PROJECT_NAME=os.getenv(
            "PROJECT_NAME", "local-dev-environments--codespaces-templates-auto-generated-"
        ),
        PROJECT_DESCRIPTION=os.getenv(
            "PROJECT_DESCRIPTION",
            "Local dev environments & Codespaces templates auto-generated per project",
        ),
        PROJECT_STACK=os.getenv("PROJECT_STACK", "python,flask"),
        VERSION=__version__,
    )

    # Register blueprints/routes
    from .routes import bp as main_bp

    app.register_blueprint(main_bp)

    return app

