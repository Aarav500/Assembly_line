import os
from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)

    # Config defaults from env
    app.config.setdefault("TRIVY_PATH", os.getenv("TRIVY_PATH", "trivy"))
    app.config.setdefault("SNYK_PATH", os.getenv("SNYK_PATH", "snyk"))
    app.config.setdefault("SNYK_TOKEN", os.getenv("SNYK_TOKEN"))
    app.config.setdefault("SCAN_TIMEOUT", int(os.getenv("SCAN_TIMEOUT", "900")))  # seconds

    from .routes import bp as routes_bp
    app.register_blueprint(routes_bp)

    return app

