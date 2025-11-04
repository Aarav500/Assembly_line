import os
from flask import Flask
from .config import load_config
from .routes import bp as routes_bp


def create_app() -> Flask:
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "..", "static"), static_url_path="/static")

    # Load configuration
    cfg = load_config()
    app.config.update(cfg)

    # Register blueprints
    app.register_blueprint(routes_bp)

    # Simple security headers
    @app.after_request
    def add_security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "no-referrer-when-downgrade")
        resp.headers.setdefault("X-XSS-Protection", "0")
        return resp

    return app

