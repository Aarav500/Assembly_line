import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, g
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from dotenv import load_dotenv

from config import Config
from models import Base, Sandbox
from services.sandbox_service import SandboxService
from utils.reaper import start_reaper


def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=Config.DB_URL,
        SANDBOX_PROVIDER=Config.SANDBOX_PROVIDER,
        COMPOSE_TEMPLATES_DIR=Config.COMPOSE_TEMPLATES_DIR,
        SANDBOX_DATA_DIR=Config.SANDBOX_DATA_DIR,
        DEFAULT_TTL_MINUTES=Config.DEFAULT_TTL_MINUTES,
        REAPER_INTERVAL_SECONDS=Config.REAPER_INTERVAL_SECONDS,
    )

    os.makedirs(Config.SANDBOX_DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(Config.SANDBOX_DATA_DIR, "sandboxes"), exist_ok=True)

    engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"], connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    Session = scoped_session(SessionFactory)

    def get_session():
        if not hasattr(g, "db"):
            g.db = Session()
        return g.db

    @app.teardown_appcontext
    def remove_session(exception=None):
        db = getattr(g, "db", None)
        if db is not None:
            db.close()
        Session.remove()

    service = SandboxService(
        session_factory=SessionFactory,
        provider_name=app.config["SANDBOX_PROVIDER"],
        data_dir=app.config["SANDBOX_DATA_DIR"],
        templates_dir=app.config["COMPOSE_TEMPLATES_DIR"],
        default_ttl_minutes=app.config["DEFAULT_TTL_MINUTES"],
    )

    start_reaper(service, interval_seconds=app.config["REAPER_INTERVAL_SECONDS"])  # background expiry cleanup

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"})

    @app.route("/api/v1/sandboxes", methods=["POST"])
    def create_sandbox():
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        template = data.get("template", "basic")
        ttl_minutes = data.get("ttl_minutes")
        env = data.get("env") or {}
        try:
            sb = service.create_sandbox(name=name, template=template, ttl_minutes=ttl_minutes, env=env)
            return jsonify(service.serialize_sandbox(sb)), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/v1/sandboxes", methods=["GET"])
    def list_sandboxes():
        s = get_session()
        items = service.list_sandboxes(s)
        return jsonify([service.serialize_sandbox(i) for i in items])

    @app.route("/api/v1/sandboxes/<sandbox_id>", methods=["GET"])
    def get_sandbox(sandbox_id):
        s = get_session()
        sb = service.get_sandbox(s, sandbox_id)
        if not sb:
            return jsonify({"error": "Not found"}), 404
        # optionally refresh status
        try:
            service.refresh_status(sb)
        except Exception:
            pass
        return jsonify(service.serialize_sandbox(sb))

    @app.route("/api/v1/sandboxes/<sandbox_id>", methods=["DELETE"])
    def delete_sandbox(sandbox_id):
        try:
            sb = service.teardown_sandbox(sandbox_id, reason="user")
            if not sb:
                return jsonify({"error": "Not found"}), 404
            return jsonify(service.serialize_sandbox(sb))
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/v1/sandboxes/<sandbox_id>/extend", methods=["POST"])
    def extend_sandbox(sandbox_id):
        data = request.get_json(silent=True) or {}
        ttl_minutes = data.get("ttl_minutes")
        if not isinstance(ttl_minutes, int) or ttl_minutes <= 0:
            return jsonify({"error": "ttl_minutes must be a positive integer"}), 400
        s = get_session()
        sb = service.get_sandbox(s, sandbox_id)
        if not sb:
            return jsonify({"error": "Not found"}), 404
        new_exp = service.extend_sandbox(sb, ttl_minutes)
        return jsonify({"id": sb.id, "expires_at": new_exp.isoformat() + "Z"})

    @app.route("/api/v1/sandboxes/<sandbox_id>/stop", methods=["POST"])
    def stop_sandbox(sandbox_id):
        try:
            sb = service.stop_sandbox(sandbox_id)
            if not sb:
                return jsonify({"error": "Not found"}), 404
            return jsonify(service.serialize_sandbox(sb))
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/v1/sandboxes/<sandbox_id>/start", methods=["POST"])
    def start_sandbox(sandbox_id):
        try:
            sb = service.start_sandbox(sandbox_id)
            if not sb:
                return jsonify({"error": "Not found"}), 404
            return jsonify(service.serialize_sandbox(sb))
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    return app



if __name__ == '__main__':
    pass
