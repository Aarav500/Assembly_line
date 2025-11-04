from functools import wraps
from flask import request, jsonify, current_app
from tenancy import get_current_tenant


def require_tenant(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        tenant = get_current_tenant()
        if not tenant or tenant.status != 'active':
            return jsonify({"error": "tenant_not_found_or_inactive"}), 401
        return f(*args, **kwargs)
    return wrapper


def is_admin_request():
    token = request.headers.get('X-Admin-Token')
    return token and token == current_app.config.get('ADMIN_TOKEN')


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_admin_request():
            return jsonify({"error": "admin_required"}), 403
        return f(*args, **kwargs)
    return wrapper

