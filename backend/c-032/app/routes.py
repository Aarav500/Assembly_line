from __future__ import annotations
import logging
from typing import Any, Dict, List
from flask import Blueprint, current_app, jsonify, request

api_bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)


def _require_admin() -> bool:
    token = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").removeprefix("Bearer ")
    cfg = current_app.config
    return token == cfg.get("ADMIN_TOKEN")


@api_bp.post("/secrets")
def create_secret():
    if not _require_admin():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    value = data.get("value")
    ttl = data.get("ttl_seconds")
    metadata = data.get("metadata") or {}
    if not name or not isinstance(name, str):
        return jsonify({"error": "name required"}), 400
    if not isinstance(value, str) or value == "":
        return jsonify({"error": "value required"}), 400
    try:
        store = current_app.extensions["secret_store"]
        store.set(name=name, plaintext=value, ttl_seconds=int(ttl) if ttl else None, metadata=metadata)
        logger.info("Secret '%s' stored", name)
        return jsonify({"status": "ok", "name": name}), 201
    except Exception as e:
        logger.exception("failed to store secret")
        return jsonify({"error": str(e)}), 500


@api_bp.get("/secrets")
def list_secrets():
    store = current_app.extensions["secret_store"]
    items = store.list()
    return jsonify({"secrets": list(items.values())})


@api_bp.get("/secrets/<name>")
def get_secret(name: str):
    store = current_app.extensions["secret_store"]
    reveal = request.args.get("reveal", "false").lower() in ("1", "true", "yes")
    if reveal and not _require_admin():
        return jsonify({"error": "unauthorized"}), 401
    try:
        item = store.get(name=name, reveal=reveal)
        return jsonify(item)
    except KeyError:
        return jsonify({"error": "not_found"}), 404
    except Exception as e:
        logging.exception("failed to get secret")
        return jsonify({"error": str(e)}), 500


@api_bp.delete("/secrets/<name>")
def delete_secret(name: str):
    if not _require_admin():
        return jsonify({"error": "unauthorized"}), 401
    store = current_app.extensions["secret_store"]
    ok = store.delete(name)
    return jsonify({"status": "deleted" if ok else "absent"})


@api_bp.post("/mask")
def mask_text():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    extra = data.get("extra_values") or []
    if not isinstance(extra, list):
        return jsonify({"error": "extra_values must be a list"}), 400
    redactor = current_app.extensions["redactor"]
    masked = redactor.redact(text, extra_values=extra)
    return jsonify({"masked": masked})


@api_bp.post("/log/demo")
def log_demo():
    data = request.get_json(silent=True) or {}
    msg = data.get("message", "")
    if not isinstance(msg, str):
        return jsonify({"error": "message must be a string"}), 400
    logger.info("demo log: %s", msg)
    # Also return masked version for client preview
    redactor = current_app.extensions["redactor"]
    return jsonify({"masked": redactor.redact(msg)})

