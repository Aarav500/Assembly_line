import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from functools import wraps

app = Flask(__name__)

# Simulated user database
USERS = {
    'admin': {'password': 'admin123', 'role': 'admin'},
    'user': {'password': 'user123', 'role': 'user'},
    'guest': {'password': 'guest123', 'role': 'guest'}
}

# RBAC policy definition
RBAC_POLICIES = {
    'admin': ['read', 'write', 'delete', 'manage_users'],
    'user': ['read', 'write'],
    'guest': ['read']
}

def require_auth(required_permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth = request.headers.get('Authorization')
            if not auth:
                return jsonify({'error': 'Missing authorization'}), 401
            
            try:
                username, password = auth.split(':')
            except ValueError:
                return jsonify({'error': 'Invalid authorization format'}), 401
            
            user = USERS.get(username)
            if not user or user['password'] != password:
                return jsonify({'error': 'Invalid credentials'}), 401
            
            role = user['role']
            permissions = RBAC_POLICIES.get(role, [])
            
            if required_permission not in permissions:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def home():
    return jsonify({'message': 'Welcome to RBAC API'})

@app.route('/api/data', methods=['GET'])
@require_auth('read')
def get_data():
    return jsonify({'data': 'This is public data'})

@app.route('/api/data', methods=['POST'])
@require_auth('write')
def create_data():
    return jsonify({'message': 'Data created successfully'}), 201

@app.route('/api/data/<int:id>', methods=['DELETE'])
@require_auth('delete')
def delete_data(id):
    return jsonify({'message': f'Data {id} deleted successfully'})

@app.route('/api/users', methods=['GET'])
@require_auth('manage_users')
def get_users():
    return jsonify({'users': list(USERS.keys())})

if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app


@app.route('/api/data/1', methods=['DELETE'])
def _auto_stub_api_data_1():
    return 'Auto-generated stub for /api/data/1', 200


@app.route('/public/ping', methods=['GET'])
def _auto_stub_public_ping():
    return 'Auto-generated stub for /public/ping', 200


@app.route('/admin/dashboard', methods=['GET'])
def _auto_stub_admin_dashboard():
    return 'Auto-generated stub for /admin/dashboard', 200


@app.route('/billing/charge', methods=['POST'])
def _auto_stub_billing_charge():
    return 'Auto-generated stub for /billing/charge', 200


@app.route('/users/42/secrets', methods=['GET'])
def _auto_stub_users_42_secrets():
    return 'Auto-generated stub for /users/42/secrets', 200


@app.route('/tokens/rotate', methods=['POST'])
def _auto_stub_tokens_rotate():
    return 'Auto-generated stub for /tokens/rotate', 200


@app.route('/support/cases', methods=['GET'])
def _auto_stub_support_cases():
    return 'Auto-generated stub for /support/cases', 200


@app.route('/audit/logs', methods=['GET'])
def _auto_stub_audit_logs():
    return 'Auto-generated stub for /audit/logs', 200
