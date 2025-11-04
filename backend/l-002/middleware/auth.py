from flask import request, jsonify, g, current_app
from functools import wraps


API_KEY_HEADER = 'X-API-Key'


def auth_init(app):
    @app.before_request
    def authenticate():
        # Health is open
        if request.path == '/health':
            return None
        # Try API key
        api_key = request.headers.get(API_KEY_HEADER)
        if not api_key:
            # allow anonymous for listing? we require auth except health and maybe index
            g.user = None
            return None
        user = current_app.policy_engine.get_user_by_api_key(api_key)
        if not user:
            g.user = None
            return None
        g.user = user
        return None


def require_permission(action: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = getattr(g, 'user', None)
            if user is None:
                return jsonify({"error": "unauthorized", "message": f"Missing or invalid {API_KEY_HEADER}"}), 401
            path = kwargs.get('secret_path') or ''
            if action == 'list' and not path:
                # listing over prefix - check if user has any list permissions
                # we defer final filtering to route handler, but need at least one list rule
                # If user has no roles, deny
                roles = user.get('roles', [])
                if not roles:
                    return jsonify({"error": "forbidden", "message": "No roles"}), 403
                # Soft allow - detailed checks done later per path
                return fn(*args, **kwargs)
            if not current_app.policy_engine.is_allowed(user, action, path):
                return jsonify({"error": "forbidden", "message": f"{action} not permitted for path"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

