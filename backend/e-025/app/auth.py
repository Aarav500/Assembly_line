import secrets
from functools import wraps
from flask import request, abort
from .db import db
from .models import Team
from .config import Config


def generate_api_key():
    return secrets.token_hex(24)


def get_team_from_api_key(api_key: str):
    if not api_key:
        return None
    return Team.query.filter_by(api_key=api_key).first()


def require_team(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        team = get_team_from_api_key(api_key)
        if not team:
            abort(401, description='Invalid or missing API key')
        request.team = team
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        admin_key = request.headers.get('X-Admin-Key')
        if not admin_key or admin_key != Config.ADMIN_API_KEY:
            abort(403, description='Admin key required')
        return f(*args, **kwargs)
    return wrapper

