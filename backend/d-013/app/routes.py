from __future__ import annotations
from flask import Blueprint, jsonify, current_app, request
from functools import wraps

main_bp = Blueprint("main", __name__)


def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        policy = current_app.extensions["policy"]
        if not policy.require_auth:
            return fn(*args, **kwargs)
        key = request.headers.get(policy.auth_header)
        if not policy.validate_api_key(key):
            return jsonify({
                "error": "unauthorized",
                "message": "Missing or invalid API key",
                "header": policy.auth_header,
            }), 401
        return fn(*args, **kwargs)
    return wrapper


@main_bp.get("/")
def index():
    policy = current_app.extensions["policy"]
    summary = {
        "env": current_app.config.get("APP_ENV"),
        "require_auth": policy.require_auth,
        "rate_limit": {
            "enabled": policy.rate_limit_enabled,
            "requests": policy.rate_limit_requests,
            "window_seconds": policy.rate_limit_window,
        },
        "allowed_origins": policy.allowed_origins,
        "feature_flags": policy.feature_flags,
    }
    return jsonify({
        "app": "environment-overlays-for-devstageprod-with-policy-difference",
        "summary": summary,
    })


@main_bp.get("/data")
@auth_required
def data():
    policy = current_app.extensions["policy"]
    api_key = request.headers.get(policy.auth_header)
    principal = None
    if api_key and policy.validate_api_key(api_key):
        principal = f"key:{api_key[:6]}****"
    else:
        principal = f"ip:{request.remote_addr}"
    return jsonify({
        "message": "secure data",
        "principal": principal,
    })


@main_bp.get("/experimental")
def experimental():
    policy = current_app.extensions["policy"]
    if not policy.flag_enabled("experimental_endpoint"):
        return jsonify({"error": "not_found"}), 404
    return jsonify({"message": "experimental feature enabled"})


@main_bp.get("/health")
def health():
    return jsonify({"status": "ok"})

