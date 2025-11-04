from flask import Blueprint, request, jsonify
from ..services.notification_service import service

bp = Blueprint("events", __name__, url_prefix="/api/events")


@bp.post("")
def create_event():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId")
    category = payload.get("category")
    message = payload.get("message")
    channels = payload.get("channels")

    if not user_id or not category or not message:
        return jsonify({"error": "userId, category, and message are required"}), 400

    try:
        result = service.record_event(user_id=int(user_id), category=str(category), message=str(message), channels=channels)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

