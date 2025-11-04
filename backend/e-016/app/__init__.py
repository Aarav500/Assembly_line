import os
import logging
from flask import Flask, jsonify
from .config import Config
from .models import db
from .routes import api_bp
from .services.scheduler import init_scheduler, load_jobs_from_db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure data directories exist
    os.makedirs(os.path.dirname(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")), exist_ok=True) if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite") else None
    os.makedirs(app.config["SNAPSHOT_DIR"], exist_ok=True)
    os.makedirs(app.config["RESTORE_DIR"], exist_ok=True)

    # Logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')

    # Extensions
    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Scheduler
    init_scheduler(app)
    with app.app_context():
        load_jobs_from_db()

    # Blueprints
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app

