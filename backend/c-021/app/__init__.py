import os
from flask import Flask, jsonify


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    # Blueprints
    from .routes.health import bp as health_bp
    from .routes.tasks import bp as tasks_bp

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(tasks_bp, url_prefix="/api")

    # Error handlers (JSON)
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request"}), 400

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app

