import os
import secrets
from functools import wraps
from flask import request, g, jsonify
from database import db
from models import User


def generate_api_key():
    return secrets.token_hex(24)


def get_current_user():
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return None
    return User.query.filter_by(api_key=api_key, active=True).first()


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        if user.role != 'admin':
            return jsonify({'error': 'Forbidden: admin required'}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return wrapper

