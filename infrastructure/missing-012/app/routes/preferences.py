from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models import User
from ..services.notification_service import service

bp = Blueprint("preferences", __name__, url_prefix="/api/preferences")


@bp.get("")
def get_preferences():
    user_id = request.args.get("userId", type=int)
    if not user_id:
        return jsonify({"error": "userId query param is required"}), 400
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    prefs = service.get_or_create_preferences(user)
    return jsonify(service.serialize_preferences(prefs))


@bp.put("")
def update_preferences():
    user_id = request.args.get("userId", type=int)
    if not user_id:
        return jsonify({"error": "userId query param is required"}), 400

    user = User.query.get(user_id)
    if not user:
        # Allow creating a minimal new user if not exists, with timezone/email etc from payload
        payload = request.get_json(silent=True) or {}
        user = service.get_or_create_user(None, email=payload.get("email"), phone=payload.get("phone"), push_token=payload.get("pushToken"), timezone=payload.get("timezone"))
        db.session.commit()

    payload = request.get_json(silent=True) or {}
    try:
        prefs = service.update_preferences(user, payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(service.serialize_preferences(prefs))

