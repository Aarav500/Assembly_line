from functools import wraps
from flask import request, jsonify, g


ROLES = {'admin', 'user', 'auditor'}


def get_user_from_headers(headers):
    user_id = headers.get('X-User-Id', 'anonymous')
    role = headers.get('X-User-Role', 'user').lower()
    tenant_id = headers.get('X-Tenant-Id')
    if role not in ROLES:
        role = 'user'
    return {
        'user_id': user_id,
        'role': role,
        'tenant_id': tenant_id
    }


def require_roles(roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = getattr(g, 'user', None)
            if not user or user['role'] not in roles:
                return jsonify({'error': 'forbidden'}), 403
            if user['role'] == 'user' and not user['tenant_id']:
                return jsonify({'error': 'tenant_required_for_user_role'}), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator


def role_allows_key_metadata(user, key_obj):
    if user['role'] == 'admin':
        return True
    if user['role'] == 'auditor':
        return True
    if user['role'] == 'user' and user['tenant_id'] == key_obj.tenant_id:
        return True
    return False


def role_allows_audit_access(user):
    return user['role'] in ('admin', 'auditor')

