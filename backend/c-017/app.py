import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from functools import wraps
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Mock user database with RBAC
users_db = {
    'admin@example.com': {
        'password': generate_password_hash('admin123'),
        'role': 'admin',
        'permissions': ['read', 'write', 'delete']
    },
    'user@example.com': {
        'password': generate_password_hash('user123'),
        'role': 'user',
        'permissions': ['read']
    }
}

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token.split(' ')[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = data['email']
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated

def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated(current_user, *args, **kwargs):
            user_data = users_db.get(current_user)
            if not user_data or user_data['role'] != required_role:
                return jsonify({'message': 'Insufficient permissions'}), 403
            return f(current_user, *args, **kwargs)
        return decorated
    return decorator

def permission_required(required_permission):
    def decorator(f):
        @wraps(f)
        def decorated(current_user, *args, **kwargs):
            user_data = users_db.get(current_user)
            if not user_data or required_permission not in user_data['permissions']:
                return jsonify({'message': 'Insufficient permissions'}), 403
            return f(current_user, *args, **kwargs)
        return decorated
    return decorator

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'message': 'Email and password required'}), 400
    
    user = users_db.get(email)
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'message': 'Invalid credentials'}), 401
    
    token = jwt.encode({
        'email': email,
        'role': user['role'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    return jsonify({
        'token': token,
        'role': user['role'],
        'permissions': user['permissions']
    }), 200

@app.route('/auth/oauth2/authorize', methods=['GET'])
def oauth2_authorize():
    # Mock OAuth2 authorization endpoint
    client_id = request.args.get('client_id')
    redirect_uri = request.args.get('redirect_uri')
    state = request.args.get('state')
    
    if not client_id or not redirect_uri:
        return jsonify({'message': 'Missing required parameters'}), 400
    
    # In production, redirect to login page and get user consent
    auth_code = jwt.encode({
        'client_id': client_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    return jsonify({
        'authorization_code': auth_code,
        'state': state,
        'redirect_uri': redirect_uri
    }), 200

@app.route('/auth/oauth2/token', methods=['POST'])
def oauth2_token():
    data = request.get_json()
    grant_type = data.get('grant_type')
    code = data.get('code')
    
    if grant_type != 'authorization_code' or not code:
        return jsonify({'message': 'Invalid grant type or code'}), 400
    
    try:
        jwt.decode(code, app.config['SECRET_KEY'], algorithms=['HS256'])
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid authorization code'}), 401
    
    access_token = jwt.encode({
        'email': 'oauth_user@example.com',
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    return jsonify({
        'access_token': access_token,
        'token_type': 'Bearer',
        'expires_in': 3600
    }), 200

@app.route('/auth/sso/saml', methods=['POST'])
def sso_saml():
    # Mock SAML SSO endpoint
    data = request.get_json()
    saml_response = data.get('SAMLResponse')
    
    if not saml_response:
        return jsonify({'message': 'SAML response required'}), 400
    
    # In production, validate SAML response
    token = jwt.encode({
        'email': 'sso_user@example.com',
        'role': 'user',
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    return jsonify({'token': token}), 200

@app.route('/api/protected', methods=['GET'])
@token_required
def protected_route(current_user):
    return jsonify({
        'message': 'Access granted',
        'user': current_user
    }), 200

@app.route('/api/admin', methods=['GET'])
@token_required
@role_required('admin')
def admin_route(current_user):
    return jsonify({
        'message': 'Admin access granted',
        'user': current_user
    }), 200

@app.route('/api/write', methods=['POST'])
@token_required
@permission_required('write')
def write_route(current_user):
    return jsonify({
        'message': 'Write operation successful',
        'user': current_user
    }), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


def create_app():
    return app
