import os
from flask import Flask, jsonify
from .config import Config
from .db import db
from .models import init_models
from .routes.assets import assets_bp
from .routes.scans import scans_bp
from .routes.findings import findings_bp
from .routes.rules import rules_bp
from .routes.remediations import remediations_bp
from .routes.reports import reports_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    db.init_app(app)

    with app.app_context():
        init_models()
        db.create_all()

    # Blueprints
    app.register_blueprint(assets_bp, url_prefix="/api/assets")
    app.register_blueprint(scans_bp, url_prefix="/api/scans")
    app.register_blueprint(findings_bp, url_prefix="/api/findings")
    app.register_blueprint(rules_bp, url_prefix="/api/rules")
    app.register_blueprint(remediations_bp, url_prefix="/api/remediations")
    app.register_blueprint(reports_bp, url_prefix="/api/reports")

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not_found"}), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad_request"}), 400

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "server_error"}), 500

    return app

