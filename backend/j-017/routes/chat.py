from flask import Blueprint, request, jsonify
from models import User, Profile
from services.ai import generate_response

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')


@chat_bp.post('')
def chat():
    payload = request.get_json(force=True) or {}
    user_id = payload.get('user_id')
    message = payload.get('message')
    profile_id = payload.get('profile_id')
    profile_name = payload.get('profile_name')
    model = payload.get('model')  # optional override

    if not message or not isinstance(message, str):
        return jsonify({"error": "message is required and must be a string"}), 400

    profile = None

    if profile_id is not None:
        profile = Profile.query.get(profile_id)
        if profile is None:
            return jsonify({"error": "profile_id not found"}), 404

    elif profile_name:
        profile = Profile.query.filter_by(name=profile_name).first()
        if profile is None:
            return jsonify({"error": "profile_name not found"}), 404

    elif user_id is not None:
        user = User.query.get(user_id)
        if user is None:
            return jsonify({"error": "user not found"}), 404
        if not user.active_profile:
            return jsonify({"error": "user has no active profile set"}), 400
        profile = user.active_profile

    else:
        return jsonify({"error": "provide user_id or profile_id/profile_name"}), 400

    result = generate_response(message=message, profile=profile, model_override=model)

    return jsonify({
        "reply": result.get("reply"),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "usage": result.get("usage"),
        "profile": profile.to_dict(),
    })

