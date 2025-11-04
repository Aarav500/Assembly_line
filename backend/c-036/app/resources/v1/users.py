from __future__ import annotations
from flask import Blueprint, jsonify, request
from ...services.users_service import users_service
from ...compat import adapt_users_list_to_version, adapt_user_to_version, adapt_request_payload_to_v2
from ...errors import ApiError

bp = Blueprint('users_v1', __name__, url_prefix='/api/v1')


@bp.get('/users')
def list_users_v1():
    users = users_service().list_users()
    adapted = adapt_users_list_to_version(users, 'v1')
    return jsonify(adapted)


@bp.get('/users/<int:user_id>')
def get_user_v1(user_id: int):
    user = users_service().get_user(user_id)
    if not user:
        from ...errors import NotFound
        raise NotFound()
    adapted = adapt_user_to_version(user, 'v1')
    return jsonify(adapted)


@bp.post('/users')
def create_user_v1():
    data = request.get_json(silent=True) or {}
    canonical = adapt_request_payload_to_v2('v1', data)
    if not canonical.get('first_name') and not canonical.get('last_name'):
        raise ApiError("Missing 'name' field", code=400)
    created = users_service().create_user(canonical)
    adapted = adapt_user_to_version(created, 'v1')
    return jsonify(adapted), 201

