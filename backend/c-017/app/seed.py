from sqlalchemy.exc import IntegrityError
from .extensions import db
from .models import Role, Permission, User
from .utils.passwords import hash_password


def _get_or_create(model, defaults=None, **kwargs):
    instance = db.session.query(model).filter_by(**kwargs).one_or_none()
    if instance:
        return instance, False
    params = dict(kwargs)
    if defaults:
        params.update(defaults)
    instance = model(**params)
    db.session.add(instance)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        instance = db.session.query(model).filter_by(**kwargs).one()
        return instance, False
    return instance, True


def seed_data(app):
    with app.app_context():
        # Roles
        admin_role, _ = _get_or_create(Role, name="admin", defaults={"description": "Administrator"})
        user_role, _ = _get_or_create(Role, name="user", defaults={"description": "Standard user"})

        # Permissions
        view_secret, _ = _get_or_create(Permission, name="view:secret", defaults={"description": "View secret resources"})
        manage_users, _ = _get_or_create(Permission, name="manage:users", defaults={"description": "Manage users"})

        # Attach permissions to admin
        if view_secret not in admin_role.permissions:
            admin_role.permissions.append(view_secret)
        if manage_users not in admin_role.permissions:
            admin_role.permissions.append(manage_users)
        db.session.commit()

        # Default admin user
        admin_email = app.config.get("ADMIN_EMAIL", "admin@example.com").lower()
        admin_password = app.config.get("ADMIN_PASSWORD", "Admin123!")

        admin_user, created = _get_or_create(User, email=admin_email)
        if created or not admin_user.password_hash:
            admin_user.name = admin_user.name or "Administrator"
            admin_user.password_hash = hash_password(admin_password)
        if admin_role not in admin_user.roles:
            admin_user.roles.append(admin_role)
        db.session.commit()

