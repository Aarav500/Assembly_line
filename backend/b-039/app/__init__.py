import os
from flask import Flask, jsonify
from .models import db, Policy
from .routes import api_bp
from .maintenance import start_scheduler
from config import Config


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        # Ensure a default policy exists
        _ensure_default_policy()

    # Blueprints
    app.register_blueprint(api_bp, url_prefix="/api")

    # JSON error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "detail": str(e)}), 400

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    # Start background maintenance scheduler (if enabled)
    start_scheduler(app)

    return app


def _ensure_default_policy():
    default = Policy.query.filter_by(name="default").first()
    if not default:
        default = Policy(
            name="default",
            description="Default policy with no automatic archival/purge",
            auto_archive_after_days=None,
            auto_purge_after_days=None,
            purge_hard=False,
            active=True,
        )
        db.session.add(default)
        db.session.commit()

