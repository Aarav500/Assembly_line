from functools import wraps
from flask import g, abort
from models import ProjectMember, Permission, Role, db


def user_has_project_permission(user, project, permission_name):
    if not user:
        return False
    if user.is_admin:
        return True
    if not project:
        return False
    membership = ProjectMember.query.filter_by(project_id=project.id, user_id=user.id).first()
    if not membership:
        return False
    role = membership.role
    return any(p.name == permission_name for p in role.permissions)


def requires_project_permission(permission_name):
    def decorator(f):
        @wraps(f)
        def wrapper(project_id, *args, **kwargs):
            from models import Project
            project = Project.query.get_or_404(project_id)
            if not user_has_project_permission(g.user, project, permission_name):
                abort(403)
            return f(project_id, *args, **kwargs)
        return wrapper
    return decorator


def available_roles():
    return Role.query.order_by(Role.name.asc()).all()

