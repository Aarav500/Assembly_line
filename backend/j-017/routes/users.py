from flask import Blueprint, request, jsonify
from database import db
from models import User, Profile

users_bp = Blueprint('users', __name__, url_prefix='/users')


@users_bp.post('')
def create_user():
    payload = request.get_json(force=True) or {}
    username = payload.get('username')
    active_profile_id = payload.get('active_profile_id')

    if not username:
        return jsonify({"error": "username is required"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "username already exists"}), 400

    user = User(username=username)

    if active_profile_id is not None:
        profile = Profile.query.get(active_profile_id)
        if profile is None:
            return jsonify({"error": "active_profile_id not found"}), 404
        user.active_profile = profile

    db.session.add(user)
    db.session.commit()

    return jsonify(user.to_dict()), 201


@users_bp.get('/<int:user_id>')
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())


@users_bp.put('/<int:user_id>/profile')
def set_user_profile(user_id):
    user = User.query.get_or_404(user_id)
    payload = request.get_json(force=True) or {}
    profile_id = payload.get('profile_id')

    if profile_id is None:
        return jsonify({"error": "profile_id is required"}), 400

    profile = Profile.query.get(profile_id)
    if profile is None:
        return jsonify({"error": "profile not found"}), 404

    user.active_profile = profile
    db.session.commit()

    return jsonify(user.to_dict())

