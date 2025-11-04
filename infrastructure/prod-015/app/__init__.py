import os
import uuid
from flask import Flask, g, request, jsonify
from .config import Config
from .extensions import db
from .models import AuditChainState
from .routes import bp as api_bp
from .audit import after_request_log_api_call, register_audit_listeners, init_chain_state

def create_app(config_object: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        init_chain_state()

    # request id middleware
    @app.before_request
    def assign_request_id():
        rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        g.request_id = rid

    @app.after_request
    def add_request_id_header(response):
        response.headers["X-Request-Id"] = getattr(g, "request_id", "unknown")
        return response

    # Audit API call logging
    app.after_request(after_request_log_api_call)

    # Register SQLAlchemy change listeners
    register_audit_listeners()

    # Blueprints
    app.register_blueprint(api_bp)

    # Health
    @app.route("/healthz", methods=["GET"])  # simple health endpoint
    def healthz():
        try:
            # quick DB check
            db.session.execute(db.text("SELECT 1"))
            return {"status": "ok"}
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 500

    return app

