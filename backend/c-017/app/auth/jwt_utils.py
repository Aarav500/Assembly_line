import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Optional

import jwt
from flask import current_app, request, jsonify, g

from ..extensions import db
from ..models import TokenBlocklist, User


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _exp(delta_seconds: int) -> datetime:
    return _now() + timedelta(seconds=delta_seconds)


def create_token(user: User, token_type: str = "access") -> str:
    assert token_type in {"access", "refresh"}
    cfg = current_app.config
    jti = str(uuid.uuid4())
    payload = {
        "jti": jti,
        "sub": str(user.id),
        "typ": token_type,
        "iat": int(_now().timestamp()),
        "nbf": int(_now().timestamp()),
        "iss": cfg.get("JWT_ISSUER", "auth-rbac-scaffold"),
        "roles": [r.name for r in user.roles],
        "perms": user.permissions,
        "email": user.email,
        "name": user.name,
    }
    if token_type == "access":
        payload["exp"] = int(_exp(cfg.get("JWT_ACCESS_EXPIRES", 3600)).timestamp())
    else:
        payload["exp"] = int(_exp(cfg.get("JWT_REFRESH_EXPIRES", 2592000)).timestamp())

    token = jwt.encode(payload, cfg["JWT_SECRET_KEY"], algorithm=cfg.get("JWT_ALGORITHM", "HS256"))
    return token


def decode_token(token: str) -> dict:
    cfg = current_app.config
    try:
        payload = jwt.decode(
            token,
            cfg["JWT_SECRET_KEY"],
            algorithms=[cfg.get("JWT_ALGORITHM", "HS256")],
            options={"require": ["exp", "iat", "nbf", "jti", "sub", "typ"]},
            issuer=cfg.get("JWT_ISSUER", None) or None,
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise AuthError("Token has expired", 401) from e
    except jwt.InvalidTokenError as e:
        raise AuthError("Invalid token", 401) from e


def is_token_revoked(jti: str) -> bool:
    if not jti:
        return True
    entry = db.session.query(TokenBlocklist).filter_by(jti=jti).one_or_none()
    return bool(entry and entry.revoked)


def token_required(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = parts[1]
        try:
            payload = decode_token(token)
        except AuthError as e:
            return jsonify({"error": e.message}), e.status_code

        if is_token_revoked(payload.get("jti")):
            return jsonify({"error": "Token has been revoked"}), 401

        # Load user fresh from DB (ensures RBAC changes reflect immediately)
        user = db.session.get(User, int(payload.get("sub"))) if payload.get("sub") else None
        if not user or not user.is_active:
            return jsonify({"error": "User not found or inactive"}), 401

        g.current_user = user
        g.jwt_payload = payload
        return fn(*args, **kwargs)

    return wrapper


def revoke_token(jti: str, token_type: str, user_id: Optional[int]) -> None:
    if not jti:
        return
    if is_token_revoked(jti):
        return
    rec = TokenBlocklist(jti=jti, token_type=token_type, user_id=user_id, revoked=True)
    db.session.add(rec)
    db.session.commit()


def extract_token_from_request(token_type: str = "access") -> Optional[str]:
    # Primarily from Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
    # Fallback: JSON body
    if request.is_json:
        token = request.json.get(f"{token_type}_token")
        if token:
            return token
    return None

