import secrets
from functools import wraps
from flask import request, jsonify, g
from .models import ApiKey


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def _extract_api_key_from_request():
    # Supports X-API-Key header or Authorization: Bearer <key>
    key = request.headers.get('X-API-Key')
    if key:
        return key.strip()
    auth = request.headers.get('Authorization')
    if auth and auth.lower().startswith('bearer '):
        return auth.split(' ', 1)[1].strip()
    return None


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        key = _extract_api_key_from_request()
        if not key:
            return jsonify({"error": "missing_api_key", "message": "Provide X-API-Key or Authorization: Bearer <key>"}), 401
        api_key = ApiKey.query.filter_by(key=key).first()
        if not api_key:
            return jsonify({"error": "invalid_api_key", "message": "API key not found"}), 401
        g.api_key = api_key
        g.user = api_key.user
        g.tenant = api_key.tenant
        return fn(*args, **kwargs)
    
    return wrapper

