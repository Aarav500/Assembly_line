from flask import Blueprint, request, jsonify
from werkzeug.exceptions import BadRequest
from auth.service import (
    register_user,
    login,
    refresh_tokens,
    validate_access_token,
    logout,
    logout_all,
    list_sessions,
    revoke_session,
    get_user_by_id,
    AuthError,
)


auth_bp = Blueprint("auth", __name__)
protected_bp = Blueprint("protected", __name__)


@auth_bp.errorhandler(AuthError)
def handle_auth_error(err: AuthError):
    resp = {"error": err.code, "message": err.message}
    return jsonify(resp), err.status


@auth_bp.post("/register")
def register():
    body = request.get_json(force=True, silent=True) or {}
    username = body.get("username")
    password = body.get("password")
    user = register_user(username, password)
    return jsonify({"user": {"id": user["id"], "username": user["username"], "created_at": user["created_at"]}}), 201


@auth_bp.post("/login")
def login_route():
    body = request.get_json(force=True, silent=True) or {}
    username = body.get("username")
    password = body.get("password")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    result = login(username, password, ip, ua)
    return jsonify(result)


@auth_bp.post("/refresh")
def refresh_route():
    body = request.get_json(force=True, silent=True) or {}
    token = body.get("refresh_token")
    if not token:
        raise BadRequest("refresh_token is required")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    tokens = refresh_tokens(token, ip, ua)
    return jsonify(tokens)


def _get_bearer_token() -> str:
    auth = request.headers.get("Authorization", "")
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return ""


@protected_bp.before_app_request
def _noop():
    # placeholder for global hooks
    pass


@protected_bp.get("/me")
def me():
    token = _get_bearer_token()
    claims = validate_access_token(token)
    user = get_user_by_id(claims.get("sub"))
    return jsonify({"user": {"id": user.get("id"), "username": user.get("username")}, "session_id": claims.get("sid")})


@auth_bp.post("/logout")
def logout_route():
    token = _get_bearer_token()
    claims = validate_access_token(token)
    logout(claims)
    return jsonify({"message": "logged out"})


@auth_bp.post("/logout-all")
def logout_all_route():
    token = _get_bearer_token()
    claims = validate_access_token(token)
    logout_all(claims.get("sub"))
    return jsonify({"message": "logged out from all sessions"})


@protected_bp.get("/sessions")
def sessions_route():
    token = _get_bearer_token()
    claims = validate_access_token(token)
    sessions = list_sessions(claims.get("sub"))
    return jsonify({"sessions": sessions})


@protected_bp.post("/sessions/<session_id>/revoke")
def revoke_session_route(session_id: str):
    token = _get_bearer_token()
    claims = validate_access_token(token)
    # Only allow revoking own session
    sessions = list_sessions(claims.get("sub"))
    if not any(s.get("session_id") == session_id for s in sessions):
        return jsonify({"error": "not_found", "message": "session not found"}), 404
    revoke_session(session_id)
    return jsonify({"message": "session revoked"})

