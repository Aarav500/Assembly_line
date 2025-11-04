from flask import Blueprint, jsonify, request

bp = Blueprint('main', __name__)

@bp.get('/')
def index():
    return jsonify(message='Hello, world!')

@bp.get('/api/items/<int:item_id>')
def get_item(item_id: int):
    return jsonify(id=item_id, name=f'Item {item_id}')

@bp.get('/api/users/<uuid:user_id>')
def get_user(user_id):
    return jsonify(id=str(user_id))

@bp.get('/api/search/<path:q>')
def search(q: str):
    return jsonify(query=q)

@bp.post('/api/echo')
def echo():
    data = request.get_json(silent=True) or {}
    return jsonify(data)

