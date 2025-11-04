from flask import Blueprint, jsonify

bp = Blueprint("main", __name__)


@bp.get("/api/health")
def health() -> tuple[dict, int]:
    return jsonify({"status": "ok"}), 200

