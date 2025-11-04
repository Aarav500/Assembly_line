"""
Application package initialization and factory.

Developer explanation:
- We use the Application Factory pattern so that the app can be configured dynamically
  (different configs for dev/test/prod) and easily tested.
- This module exposes a create_app(config_name: str | None) -> Flask function, which
  initializes extensions, registers blueprints, and sets up error handlers.
- Keeping side effects (like creating the app) inside the factory avoids importing issues
  in tests and makes the code more modular.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from flask import Flask

from .config import CONFIG_MAP, BaseConfig
from .errors import register_error_handlers
from .routes import main_bp


def create_app(config_name: Optional[str] = None) -> Flask:
    """
    Create and configure the Flask app instance.

    Args:
        config_name: Optional explicit configuration name ("development", "testing", "production").
                     If not provided, we derive it from APP_ENV or FLASK_ENV env vars.

    Returns:
        A configured Flask application instance.

    Developer notes:
    - Order matters: configure app -> init extensions (if any) -> register blueprints -> register errors.
    - We keep logging setup minimal but production-safe.
    """
    app = Flask(__name__, instance_relative_config=True)

    # 1) Load configuration
    # Allow override via function arg, then APP_ENV, then FLASK_ENV, defaulting to development.
    env_name = (
        (config_name or os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "development")
        .strip()
        .lower()
    )
    config_cls = CONFIG_MAP.get(env_name, BaseConfig)
    app.config.from_object(config_cls)

    # 2) Instance folder (for writable files like SQLite or logs); ensure it exists.
    try:
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    except OSError:
        # Not fatal; log a warning. Some environments may not allow writing.
        app.logger.warning("Could not ensure instance folder exists: %s", app.instance_path)

    # 3) Logging setup
    _configure_logging(app)

    # 4) Register blueprints (modular route grouping)
    app.register_blueprint(main_bp)

    # 5) Register error handlers (centralized error responses)
    register_error_handlers(app)

    # 6) Simple startup log to confirm configuration
    app.logger.info(
        "App created with config=%s (DEBUG=%s)", config_cls.__name__, app.config.get("DEBUG")
    )

    return app


def _configure_logging(app: Flask) -> None:
    """
    Configure application logging with sensible defaults.

    Developer explanation:
    - In development, Flask's debug logger is sufficient.
    - In production, we attach a RotatingFileHandler to avoid log files growing unbounded.
    - Log level is controlled by the configuration's LOG_LEVEL.
    """
    log_level = app.config.get("LOG_LEVEL", logging.INFO)
    app.logger.setLevel(log_level)

    # If running under a WSGI server, it may have its own handlers; avoid duplicates.
    if app.logger.handlers and not app.config.get("FORCE_LOG_HANDLER"):
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if app.config.get("ENV") == "production":
        # Write to instance/logs/app.log by default
        log_dir = Path(app.instance_path) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "app.log", maxBytes=1_000_000, backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        app.logger.addHandler(file_handler)
    else:
        # Stream to stderr in dev/testing for visibility
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(log_level)
        stream_handler.setFormatter(formatter)
        app.logger.addHandler(stream_handler)

