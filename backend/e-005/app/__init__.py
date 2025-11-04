import os
import threading
from flask import Flask
from .config import Config
from .models import db
from .routes import api_bp
from .scheduler import start_scheduler_if_enabled


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    # Init DB
    db.init_app(app)
    with app.app_context():
        db.create_all()

    # Register routes
    app.register_blueprint(api_bp)

    # Start scheduler thread if enabled
    start_scheduler_if_enabled(app)

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app

