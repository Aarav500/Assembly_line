from __future__ import annotations
from flask import Blueprint, request, jsonify, g
from ..services.users_service import users_service
from ..compat import adapt_users_list_to_version, adapt_user_to_version, adapt_request_payload_to_v2
from ..errors import ApiError

bp = Blueprint('default_api', __name__, url_prefix='/api')


@bp.get('/users')
def list_users_negotiated():
    version = getattr(g, 'api_version', 'v2')
    users = users_service().list_users()
    adapted = adapt_users_list_to_version(users, version)
    return jsonify(adapted)


@bp.post('/users')
def create_user_negotiated():
    version = getattr(g, 'api_version', 'v2')
    data = request.get_json(silent=True) or {}
    canonical = adapt_request_payload_to_v2(version, data)
    if not canonical.get('first_name') and not canonical.get('last_name'):
        raise ApiError("Missing name fields", code=400)
    created = users_service().create_user(canonical)
    adapted = adapt_user_to_version(created, version)
    return jsonify(adapted), 201


@bp.get('/users/<int:user_id>')
def get_user_negotiated(user_id: int):
    version = getattr(g, 'api_version', 'v2')
    user = users_service().get_user(user_id)
    if not user:
        from ..errors import NotFound
        raise NotFound()
    adapted = adapt_user_to_version(user, version)
    return jsonify(adapted)

