from flask import Blueprint, jsonify, request

api_bp = Blueprint('api', __name__)

@api_bp.route('/items', methods=['GET'])
def get_items():
    items = [
        {'id': 1, 'name': 'Item 1'},
        {'id': 2, 'name': 'Item 2'}
    ]
    return jsonify(items)

@api_bp.route('/items', methods=['POST'])
def create_item():
    data = request.get_json()
    return jsonify({'id': 3, 'name': data.get('name', 'New Item')}), 201
