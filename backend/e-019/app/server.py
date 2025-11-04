import json
import os
from functools import wraps
from typing import Any, Dict
from flask import Flask, jsonify, request, abort

from .config import Config
from .failover import FailoverManager
from . import state_manager


cfg = Config()
# Validate config lazily to allow health endpoint even if misconfigured
try:
    cfg.validate()
except Exception:
    pass
manager = FailoverManager(cfg)


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if cfg.api_token:
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                abort(401)
            token = auth.split(" ", 1)[1]
            if token != cfg.api_token:
                abort(403)
        return f(*args, **kwargs)
    return wrapper


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health() -> Any:
        return jsonify({"status": "ok", "app": cfg.app_name})

    @app.get("/status")
    @require_auth
    def status() -> Any:
        try:
            cfg.validate()
            eval = manager.evaluate()
            return jsonify({
                "app": cfg.app_name,
                "active_region": eval["active_region"],
                "primary_ok": eval["primary_ok"],
                "secondary_ok": eval["secondary_ok"],
                "state": eval["state"],
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post("/failover")
    @require_auth
    def failover() -> Any:
        target = request.args.get("target")
        try:
            cfg.validate()
            if target:
                if target not in (cfg.primary_region, cfg.secondary_region, "primary", "secondary"):
                    return jsonify({"error": "invalid target"}), 400
                if target in ("primary", "secondary"):
                    target = cfg.primary_region if target == "primary" else cfg.secondary_region
                res = manager.set_active(target, reason="api-manual")
                return jsonify(res)
            else:
                res = manager.evaluate_and_act()
                return jsonify(res)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post("/failback")
    @require_auth
    def failback() -> Any:
        try:
            cfg.validate()
            res = manager.failback()
            return jsonify(res)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post("/dns/sync")
    @require_auth
    def dns_sync() -> Any:
        try:
            cfg.validate()
            res = manager.sync_dns()
            return jsonify(res)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post("/simulate/outage")
    @require_auth
    def simulate_outage() -> Any:
        payload = request.get_json(silent=True) or {}
        region_key = payload.get("region")
        down = payload.get("down")
        if region_key not in ("primary", "secondary"):
            return jsonify({"error": "region must be 'primary' or 'secondary'"}), 400
        if down is None:
            return jsonify({"error": "down must be true or false"}), 400
        try:
            st = state_manager.set_simulated_outage(cfg.state_file, region_key, bool(down))
            return jsonify({"state": st})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    app.run(host=host, port=port)

