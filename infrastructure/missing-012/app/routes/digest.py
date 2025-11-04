from flask import Blueprint, request, jsonify
from ..services.notification_service import service

bp = Blueprint("digest", __name__, url_prefix="/api/digest")


@bp.post("/run")
def run_digest():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId")
    try:
        res = service.run_due_digests(user_id=int(user_id) if user_id is not None else None)
        return jsonify(res)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.get("/preview")
def preview_digest():
    user_id = request.args.get("userId", type=int)
    if not user_id:
        return jsonify({"error": "userId is required"}), 400
    try:
        res = service.preview_digest(user_id)
        return jsonify(res)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

