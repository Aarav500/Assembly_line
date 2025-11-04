import os
from flask import Flask

from .config import Config
from .db import Database
from .routes import bp as api_bp
from .auto_scaler import AutoScaler

_db = None
_scaler = None


def create_app():
    global _db, _scaler

    app = Flask(__name__)
    app.config.from_object(Config())

    # Initialize database
    _db = Database(app.config["DATABASE_PATH"])  # singleton-like use
    _db.migrate()

    # Register blueprints
    app.register_blueprint(api_bp, url_prefix="/api")

    # Start autoscaler once, when the app first handles a request
    @_once
    def start_scaler_once():
        nonlocal _scaler
        _scaler = AutoScaler(db=_db, config=app.config)
        _scaler.start()

    @app.before_first_request
    def start_background():
        start_scaler_once()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


def _once(func):
    # Decorator to ensure a function runs just once per process
    has_run = {"done": False}

    def wrapper(*args, **kwargs):
        if not has_run["done"]:
            has_run["done"] = True
            return func(*args, **kwargs)
    return wrapper

