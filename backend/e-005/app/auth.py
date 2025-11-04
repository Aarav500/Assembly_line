from functools import wraps
from flask import current_app, request, jsonify


def require_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        expected = current_app.config.get('API_TOKEN')
        if expected:
            auth = request.headers.get('Authorization', '')
            if not auth.startswith('Bearer '):
                return jsonify({'error': 'Unauthorized'}), 401
            token = auth.split(' ', 1)[1].strip()
            if token != expected:
                return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return wrapper

