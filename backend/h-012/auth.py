from flask import Blueprint, request, jsonify, g
from models import db, User, RoleEnum
from utils import create_access_token, log_audit, jwt_required, roles_required

bp = Blueprint("auth", __name__, url_prefix="/auth")

@bp.route("/register", methods=["POST"])
@jwt_required
@roles_required(RoleEnum.admin)
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password")
    role = data.get("role", RoleEnum.viewer)
    try:
        role = RoleEnum(role)
    except Exception:
        return jsonify({"error": "Invalid role"}), 400
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409
    user = User(email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    log_audit("user.create", resource_type="user", resource_id=user.id, success=True, message=f"Created user {email} with role {role.value}")
    return jsonify({"user": user.to_safe_dict()}), 201

@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password) or not user.is_active:
        log_audit("auth.login", resource_type="user", resource_id=email, success=False, message="Invalid credentials or inactive user")
        return jsonify({"error": "Invalid credentials"}), 401
    token = create_access_token(user)
    log_audit("auth.login", resource_type="user", resource_id=user.id, success=True, message="Login success")
    return jsonify({"access_token": token, "user": user.to_safe_dict()})

@bp.route("/me", methods=["GET"])
@jwt_required
def me():
    return jsonify({"user": g.current_user.to_safe_dict()})

