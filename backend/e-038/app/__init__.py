import os
from flask import Flask, jsonify
from .config import Config
from .extensions import db
from .routes import api_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config())

    db.init_app(app)

    with app.app_context():
        from . import models  # noqa: F401
        db.create_all()

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    return app

