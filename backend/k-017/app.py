import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import logging
from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest, Forbidden

from config import Config
from policy_engine.engine import PolicyEngine


def create_app(config: Config | None = None) -> Flask:
    app = Flask(__name__)

    cfg = config or Config.from_env()

    # Logging
    logging.basicConfig(level=getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO))
    logger = logging.getLogger("policy-agent")

    try:
        engine = PolicyEngine.from_file(cfg.POLICY_FILE)
    except FileNotFoundError:
        logger.warning("Policy file not found at %s; starting with no policies", cfg.POLICY_FILE)
        engine = PolicyEngine(policies=[])

    app.config["ENGINE"] = engine
    app.config["CFG"] = cfg

    @app.route("/health", methods=["GET"])  # liveness/readiness
    def health():
        eng: PolicyEngine = app.config["ENGINE"]
        status = {
            "status": "ok",
            "policies_loaded": len(eng.policies),
            "policy_file": cfg.POLICY_FILE,
        }
        return jsonify(status), 200

    @app.route("/policies", methods=["GET"])  # list policies
    def policies():
        eng: PolicyEngine = app.config["ENGINE"]
        return jsonify({
            "count": len(eng.policies),
            "policies": [p.to_dict(include_pattern=True) for p in eng.policies]
        }), 200

    def _extract_content_payload():
        if not request.is_json:
            raise BadRequest("Expected JSON body")
        data = request.get_json(silent=True) or {}
        content = data.get("content")
        metadata = data.get("metadata") or {}
        if content is None or not isinstance(content, str):
            raise BadRequest("Field 'content' must be a string")
        if not isinstance(metadata, dict):
            raise BadRequest("Field 'metadata' must be an object")
        return content, metadata

    @app.route("/scan", methods=["POST"])  # scan arbitrary output
    def scan():
        content, metadata = _extract_content_payload()
        eng: PolicyEngine = app.config["ENGINE"]
        result = eng.scan(content, metadata=metadata)
        return jsonify(result), 200

    @app.route("/apply", methods=["POST"])  # scan before apply
    def apply():
        content, metadata = _extract_content_payload()
        eng: PolicyEngine = app.config["ENGINE"]
        result = eng.scan(content, metadata=metadata)
        allowed = result.get("allowed", True)
        response = {
            **result,
            "applied": bool(allowed)
        }
        if allowed:
            return jsonify(response), 200
        return jsonify(response), 400

    @app.route("/reload", methods=["POST"])  # reload policies from disk
    def reload_policies():
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if app.config["CFG"].RELOAD_TOKEN and token != app.config["CFG"].RELOAD_TOKEN:
            raise Forbidden("Invalid or missing token")
        engine_path = app.config["CFG"].POLICY_FILE
        new_engine = PolicyEngine.from_file(engine_path)
        app.config["ENGINE"] = new_engine
        return jsonify({
            "status": "reloaded",
            "policies_loaded": len(new_engine.policies)
        }), 200

    return app


if __name__ == "__main__":
    cfg = Config.from_env()
    app = create_app(cfg)
    app.run(host=cfg.HOST, port=cfg.PORT)

