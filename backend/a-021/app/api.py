from __future__ import annotations
import os
from flask import Blueprint, current_app, jsonify, request
from .services.suggester import Suggester

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

_suggester: Suggester | None = None

def _get_suggester() -> Suggester:
    global _suggester
    if _suggester is None:
        blueprints_path = current_app.config.get("BLUEPRINTS_PATH")
        _suggester = Suggester(blueprints_path)
    return _suggester


@api_bp.get("/blueprints")
def list_blueprints():
    s = _get_suggester()
    return jsonify({
        "count": len(s.blueprints),
        "blueprints": [
            {
                "id": b["id"],
                "name": b["name"],
                "description": b["description"],
                "tags": b.get("tags", []),
            }
            for b in s.blueprints
        ],
    })


@api_bp.post("/suggest")
def suggest():
    if not request.is_json:
        return jsonify({"error": "Request must be application/json"}), 400

    payload = request.get_json(silent=True) or {}

    # top_k can come from query string or body
    try:
        top_k = int(request.args.get("top_k") or payload.get("top_k") or current_app.config["SUGGESTION_TOP_K"])
        top_k = max(1, min(10, top_k))
    except Exception:
        return jsonify({"error": "Invalid top_k; must be integer"}), 400

    # Basic validation
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    project = payload.get("project") or payload  # allow raw project as body

    if not isinstance(project, dict):
        return jsonify({"error": "Invalid project structure"}), 400

    suggestions = _get_suggester().suggest(project, top_k=top_k)
    return jsonify(suggestions)

