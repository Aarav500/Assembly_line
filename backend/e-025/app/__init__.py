import os
from flask import Flask, jsonify
from .config import Config
from .db import db
from .provisioner import provisioner
from .routes.health import bp as health_bp
from .routes.teams import bp as teams_bp
from .routes.environments import bp as envs_bp
from .routes.tasks import bp as tasks_bp
from .routes.audit import bp as audit_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    # Ensure data directory exists for sqlite
    if app.config.get('DATABASE_URL', '').startswith('sqlite:///'):
        path = app.config['DATABASE_URL'].replace('sqlite:////', '/').replace('sqlite:///', '')
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    db.init_app(app)

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad_request", "message": getattr(e, 'description', str(e))}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "unauthorized", "message": getattr(e, 'description', str(e))}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "forbidden", "message": getattr(e, 'description', str(e))}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not_found", "message": getattr(e, 'description', str(e))}), 404

    @app.errorhandler(409)
    def conflict(e):
        return jsonify({"error": "conflict", "message": getattr(e, 'description', str(e))}), 409

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "server_error", "message": "An unexpected error occurred."}), 500

    with app.app_context():
        db.create_all()
        provisioner.init_app(app)

    app.register_blueprint(health_bp, url_prefix='/health')
    app.register_blueprint(teams_bp, url_prefix='/api/v1')
    app.register_blueprint(envs_bp, url_prefix='/api/v1')
    app.register_blueprint(tasks_bp, url_prefix='/api/v1')
    app.register_blueprint(audit_bp, url_prefix='/api/v1')

    return app

