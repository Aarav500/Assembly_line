import os
from flask import Flask
from .routes import bp as main_bp
from config import Config


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    # Ensure workspaces dir exists
    os.makedirs(app.config["WORKSPACES_DIR"], exist_ok=True)

    app.register_blueprint(main_bp)

    @app.after_request
    def set_security_headers(resp):
        # Content Security Policy (tightened for sandboxed preview)
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "img-src 'self' data: blob: https:; "
            "font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "connect-src 'self'; "
            "frame-ancestors 'self'; "
            "object-src 'none'"
        )
        resp.headers.setdefault("Content-Security-Policy", csp)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        return resp

    return app

