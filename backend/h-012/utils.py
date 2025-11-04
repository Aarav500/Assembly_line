import os
from datetime import datetime, timedelta, timezone
from functools import wraps
import jwt
from flask import request, jsonify, g, current_app
from models import db, User, AuditLog, RoleEnum, Dataset, DatasetAccess, ClassificationEnum


def create_access_token(user: User, expires_minutes: int = 60) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=expires_minutes),
        "iat": datetime.now(tz=timezone.utc),
        "type": "access",
    }
    token = jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")
    return token


def parse_token_from_request():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return auth.split(" ", 1)[1].strip()


def jwt_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = parse_token_from_request()
        if not token:
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        try:
            payload = jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
            user_id = int(payload.get("sub"))
            user = db.session.get(User, user_id)
            if not user or not user.is_active:
                return jsonify({"error": "Invalid user"}), 401
            g.current_user = user
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*roles: RoleEnum):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user: User = getattr(g, "current_user", None)
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            if user.role not in roles:
                return jsonify({"error": "Forbidden: insufficient role"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def log_audit(action: str, resource_type: str | None = None, resource_id: str | None = None, success: bool = True, message: str | None = None):
    try:
        user = getattr(g, "current_user", None)
        log = AuditLog(
            user_id=user.id if user else None,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            success=success,
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
            user_agent=request.headers.get("User-Agent"),
            method=request.method,
            path=request.path,
            message=message,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


def user_can_read_dataset(user: User, dataset: Dataset) -> bool:
    if user.role == RoleEnum.admin:
        return True
    if dataset.owner_id == user.id:
        return True
    if dataset.classification == ClassificationEnum.public:
        return True
    if dataset.classification in (ClassificationEnum.confidential, ClassificationEnum.restricted):
        access = DatasetAccess.query.filter_by(user_id=user.id, dataset_id=dataset.id, can_read=True).first()
        return access is not None
    return False


def require_dataset_read_access(fn):
    @wraps(fn)
    def wrapper(dataset_id, *args, **kwargs):
        user: User = getattr(g, "current_user", None)
        dataset = db.session.get(Dataset, int(dataset_id))
        if not dataset:
            log_audit("dataset.read", resource_type="dataset", resource_id=dataset_id, success=False, message="Dataset not found")
            return jsonify({"error": "Dataset not found"}), 404
        if not user_can_read_dataset(user, dataset):
            log_audit("dataset.read", resource_type="dataset", resource_id=dataset_id, success=False, message="Access denied")
            return jsonify({"error": "Access denied"}), 403
        g.dataset = dataset
        return fn(dataset_id, *args, **kwargs)
    return wrapper


def is_owner_or_admin(user: User, dataset: Dataset) -> bool:
    return user.role == RoleEnum.admin or dataset.owner_id == user.id

