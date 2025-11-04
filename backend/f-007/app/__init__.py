import threading
import time
from flask import Flask
from .config import Config
from .db import init_db
from .routes import register_routes
from .handoff_worker import HandoffWorker

_worker_instance = None


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config())

    # Initialize DB
    init_db()

    # Register routes
    register_routes(app)

    # Start background worker if enabled
    global _worker_instance
    if app.config.get("HANDOFF_WORKER_ENABLED", True) and _worker_instance is None:
        _worker_instance = HandoffWorker(interval_seconds=app.config.get("HANDOFF_WORKER_INTERVAL", 30))
        _worker_instance.start()

    @app.route("/health", methods=["GET"])  # basic health check
    def health():
        return {"status": "ok"}

    return app

