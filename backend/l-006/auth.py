import os
from functools import wraps
from flask import request, current_app
from werkzeug.exceptions import Unauthorized

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization', '')
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            token = parts[1]
        expected = current_app.config.get('API_TOKEN')
        if not expected:
            # if not set, deny all for safety
            raise Unauthorized('API token not configured')
        if token != expected:
            raise Unauthorized('Invalid or missing bearer token')
        return f(*args, **kwargs)
    return wrapper

