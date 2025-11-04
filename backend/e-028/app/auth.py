import os
from functools import wraps
from flask import request, current_app, abort

def require_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token_required = current_app.config.get("REGISTRY_TOKEN")
        if token_required:
            auth = request.headers.get("Authorization", "")
            prefix = "Bearer "
            if not auth.startswith(prefix):
                abort(401, description="missing bearer token")
            provided = auth[len(prefix):].strip()
            if provided != token_required:
                abort(401, description="invalid token")
        return fn(*args, **kwargs)
    return wrapper

