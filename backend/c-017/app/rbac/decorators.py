from functools import wraps
from flask import jsonify, g
from ..auth.jwt_utils import token_required


def roles_required(*required_roles: str):
    def decorator(fn):
        @wraps(fn)
        @token_required
        def wrapper(*args, **kwargs):
            user = g.current_user
            if not any(user.has_role(r) for r in required_roles):
                return jsonify({"error": "Insufficient role"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def permissions_required(*required_permissions: str):
    def decorator(fn):
        @wraps(fn)
        @token_required
        def wrapper(*args, **kwargs):
            user_perms = set(g.current_user.permissions)
            if not set(required_permissions).issubset(user_perms):
                return jsonify({"error": "Missing required permission(s)"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

