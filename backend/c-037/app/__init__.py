from flask import Flask, jsonify, g, request

from .db import db
from .routes import api
from .tenancy import set_tenant_on_request
from .cli import register_cli


def create_app(config_object="config.Config") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)

    # Blueprints
    app.register_blueprint(api)

    # Health check
    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    # Tenancy per-request setup
    @app.before_request
    def _before_request():
        # Bypass tenant requirement for health and root
        if request.path in ("/healthz", "/"):
            return
        set_tenant_on_request()

    @app.teardown_appcontext
    def _teardown(exc=None):
        # ensure session is cleaned up, which resets connection state to pool
        db.session.remove()

    # Error handlers (basic JSON)
    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    @app.errorhandler(422)
    @app.errorhandler(500)
    def handle_error(err):
        code = getattr(err, "code", 500)
        desc = getattr(err, "description", str(err))
        return jsonify({"error": desc, "status": code}), code

    register_cli(app)
    return app

