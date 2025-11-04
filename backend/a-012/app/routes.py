from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
import uuid
from threading import Lock

bp = Blueprint("core", __name__)

# Very simple in-memory store for demo purposes only
_ITEMS: list[dict] = []
_ITEMS_LOCK = Lock()


@bp.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@bp.get("/api/version")
def version():
    return jsonify({"version": current_app.config.get("APP_VERSION", "unknown")}), 200


@bp.post("/api/echo")
def echo():
    try:
        payload = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400
    return jsonify({"echo": payload}), 200


@bp.get("/api/items")
def list_items():
    with _ITEMS_LOCK:
        items_copy = list(_ITEMS)
    return jsonify({"items": items_copy}), 200


@bp.post("/api/items")
def create_item():
    try:
        payload = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    name = payload.get("name") if isinstance(payload, dict) else None
    if not name or not isinstance(name, str):
        return jsonify({"error": "Field 'name' (string) is required"}), 400

    item = {"id": str(uuid.uuid4()), "name": name}
    with _ITEMS_LOCK:
        _ITEMS.append(item)
    return jsonify(item), 201

