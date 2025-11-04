from __future__ import annotations
from flask import Blueprint, jsonify, request
from ...services.users_service import users_service
from ...errors import ApiError

bp = Blueprint('users_v2', __name__, url_prefix='/api/v2')


@bp.get('/users')
def list_users_v2():
    return jsonify(users_service().list_users())


@bp.get('/users/<int:user_id>')
def get_user_v2(user_id: int):
    user = users_service().get_user(user_id)
    if not user:
        from ...errors import NotFound
        raise NotFound()
    return jsonify(user)


@bp.post('/users')
def create_user_v2():
    data = request.get_json(silent=True) or {}
    first = data.get('first_name')
    last = data.get('last_name')
    if not first and not last:
        raise ApiError("Provide first_name or last_name", code=400)
    created = users_service().create_user(data)
    return jsonify(created), 201

