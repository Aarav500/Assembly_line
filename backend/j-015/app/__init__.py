import os
from flask import Flask
from .config import Config
from .routes import main_bp
from .security import apply_security_headers
from .ratelimit import RateLimiter


def create_app(config_object: str | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_object or Config)

    # Register blueprints
    app.register_blueprint(main_bp)

    # Security headers
    @app.after_request
    def _set_security_headers(response):
        return apply_security_headers(response, app.config)

    # Rate limiting
    limiter = RateLimiter(
        limit_per_window=app.config.get("RATE_LIMIT_REQUESTS", 100),
        window_seconds=app.config.get("RATE_LIMIT_WINDOW", 900),
        key_func=lambda: (os.environ.get("FLASK_ENV", "prod"),),
    )

    @app.before_request
    def _apply_rate_limit():
        return limiter.check()

    return app

