import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
from functools import wraps

app = Flask(__name__)

# API versioning decorator
def version(v):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)
        wrapper._version = v
        return wrapper
    return decorator

# Version 1 endpoints
@app.route('/api/v1/users', methods=['GET'])
@version('v1')
def get_users_v1():
    return jsonify({
        'version': 'v1',
        'users': [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'}
        ]
    })

@app.route('/api/v1/users/<int:user_id>', methods=['GET'])
@version('v1')
def get_user_v1(user_id):
    return jsonify({
        'version': 'v1',
        'user': {'id': user_id, 'name': 'John'}
    })

# Version 2 endpoints with enhanced data structure (backward compatible)
@app.route('/api/v2/users', methods=['GET'])
@version('v2')
def get_users_v2():
    return jsonify({
        'version': 'v2',
        'users': [
            {'id': 1, 'name': 'John', 'email': 'john@example.com', 'created_at': '2024-01-01'},
            {'id': 2, 'name': 'Jane', 'email': 'jane@example.com', 'created_at': '2024-01-02'}
        ],
        'total': 2
    })

@app.route('/api/v2/users/<int:user_id>', methods=['GET'])
@version('v2')
def get_user_v2(user_id):
    return jsonify({
        'version': 'v2',
        'user': {
            'id': user_id,
            'name': 'John',
            'email': 'john@example.com',
            'created_at': '2024-01-01',
            'profile': {'bio': 'Software developer'}
        }
    })

# Default route redirects to latest version
@app.route('/api/users', methods=['GET'])
def get_users_default():
    version_header = request.headers.get('API-Version', 'v2')
    if version_header == 'v1':
        return get_users_v1()
    return get_users_v2()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)



def create_app():
    return app


@app.route('/api/v1/users/1', methods=['GET'])
def _auto_stub_api_v1_users_1():
    return 'Auto-generated stub for /api/v1/users/1', 200


@app.route('/api/v2/users/1', methods=['GET'])
def _auto_stub_api_v2_users_1():
    return 'Auto-generated stub for /api/v2/users/1', 200


@app.route('/api/users/1', methods=['GET'])
def _auto_stub_api_users_1():
    return 'Auto-generated stub for /api/users/1', 200
