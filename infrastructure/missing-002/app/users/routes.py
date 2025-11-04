from flask import Blueprint, request, jsonify
from flask_login import login_required
from sqlalchemy.exc import IntegrityError
from email_validator import validate_email, EmailNotValidError
from ..extensions import db
from ..models import User, Profile, Role
from ..utils import roles_required, paginate_query

admin_bp = Blueprint('admin', __name__)


@admin_bp.get('/users')
@login_required
@roles_required('admin')
def list_users():
    q = request.args.get('q', '').strip().lower()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    query = User.query
    if q:
        query = query.filter(User.email.ilike(f"%{q}%"))

    items, total, page, per_page = paginate_query(query.order_by(User.created_at.desc()), page, per_page)
    return jsonify({
        "items": [u.to_dict() for u in items],
        "total": total,
        "page": page,
        "per_page": per_page,
    })


@admin_bp.post('/users')
@login_required
@roles_required('admin')
def create_user():
    data = request.get_json(silent=True) or {}
    raw_email = (data.get('email') or '').strip()
    try:
        email = validate_email(raw_email).email.lower()
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    password = data.get('password') or ''
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already in use"}), 400

    user = User(email=email, is_active=bool(data.get('is_active', True)), is_email_verified=bool(data.get('is_email_verified', False)))
    user.set_password(password)

    profile = Profile(
        user=user,
        full_name=data.get('full_name'),
        bio=data.get('bio'),
        avatar_url=data.get('avatar_url'),
        phone=data.get('phone'),
        timezone=data.get('timezone'),
    )

    # Assign roles if provided
    roles = data.get('roles') or []
    if roles:
        role_models = Role.query.filter(Role.name.in_(roles)).all()
        user.roles = role_models
    else:
        user_role = Role.query.filter_by(name='user').first()
        if user_role:
            user.roles.append(user_role)

    db.session.add(user)
    db.session.add(profile)
    db.session.commit()

    return jsonify({"user": user.to_dict()}), 201


@admin_bp.get('/users/<int:user_id>')
@login_required
@roles_required('admin')
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({"user": user.to_dict()})


@admin_bp.put('/users/<int:user_id>')
@login_required
@roles_required('admin')
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    if 'email' in data and data['email']:
        try:
            email = validate_email(data['email']).email.lower()
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        if User.query.filter(User.email == email, User.id != user.id).first():
            return jsonify({"error": "Email already in use"}), 400
        user.email = email

    if 'password' in data and data['password']:
        if len(data['password']) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        user.set_password(data['password'])

    if 'is_active' in data:
        user.is_active = bool(data['is_active'])
    if 'is_email_verified' in data:
        user.is_email_verified = bool(data['is_email_verified'])

    profile = user.profile or Profile(user=user)
    for f in ['full_name', 'bio', 'avatar_url', 'phone', 'timezone']:
        if f in data:
            setattr(profile, f, data.get(f))
    db.session.add(profile)

    if 'roles' in data and isinstance(data['roles'], list):
        role_models = Role.query.filter(Role.name.in_(data['roles'])).all()
        user.roles = role_models

    db.session.commit()
    return jsonify({"user": user.to_dict()})


@admin_bp.delete('/users/<int:user_id>')
@login_required
@roles_required('admin')
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted"})


@admin_bp.get('/roles')
@login_required
@roles_required('admin')
def list_roles():
    roles = Role.query.order_by(Role.name.asc()).all()
    return jsonify({"roles": [r.to_dict() for r in roles]})


@admin_bp.post('/roles')
@login_required
@roles_required('admin')
def create_role():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({"error": "Role name required"}), 400
    if Role.query.filter_by(name=name).first():
        return jsonify({"error": "Role already exists"}), 400
    role = Role(name=name, description=data.get('description'))
    db.session.add(role)
    db.session.commit()
    return jsonify({"role": role.to_dict()}), 201


@admin_bp.delete('/roles/<int:role_id>')
@login_required
@roles_required('admin')
def delete_role(role_id):
    role = Role.query.get_or_404(role_id)
    db.session.delete(role)
    db.session.commit()
    return jsonify({"message": "Role deleted"})

