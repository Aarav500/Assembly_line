from flask import Blueprint, request, jsonify
from services.tiers import list_tiers, upsert_tier, get_tier
from services.users import create_user, list_users, get_user

admin_bp = Blueprint('admin', __name__, url_prefix='/v1/admin')


@admin_bp.get('/tiers')
def tiers_list():
    return jsonify({"tiers": list_tiers()})


@admin_bp.post('/tiers')
def tiers_upsert():
    payload = request.get_json(force=True)
    if not payload or not payload.get('name'):
        return jsonify({"error": "name required"}), 400
    tier = upsert_tier(payload)
    return jsonify(tier), 201


@admin_bp.post('/users')
def users_create():
    payload = request.get_json(force=True)
    email = payload.get('email')
    tier = payload.get('tier')
    if not email or not tier:
        return jsonify({"error": "email and tier required"}), 400
    user = create_user(email=email, tier=tier, billing_id=payload.get('billing_id'))
    return jsonify(user), 201


@admin_bp.get('/users')
def users_list():
    users = list_users()
    return jsonify({"users": users})


@admin_bp.get('/users/<user_id>')
def users_get(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "not found"}), 404
    return jsonify(user)

