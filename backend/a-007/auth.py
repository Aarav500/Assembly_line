from flask import Blueprint, request, session, jsonify, abort
from functools import wraps


auth_bp = Blueprint("auth", __name__)


def requires_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            if not session.get("user"):
                abort(401, description="Authentication required")
            return fn(*args, **kwargs)
        except Exception as e:
            if hasattr(e, 'code') and e.code == 401:
                raise
            abort(500, description="Internal server error")
    # tag for feature detection
    tags = getattr(fn, "__feature_tags__", set())
    tags.add("auth")
    wrapper.__feature_tags__ = tags
    wrapper.__requires_auth__ = True
    return wrapper


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        if not username or not password:
            return jsonify({"error": "username and password required"}), 400
        # demo only: accept any non-empty username/password
        session["user"] = {"username": username}
        return jsonify({"ok": True, "user": session["user"]})
    except Exception as e:
        return jsonify({"error": "Login failed"}), 500


@auth_bp.route("/logout", methods=["POST", "GET"]) 
def logout():
    try:
        session.pop("user", None)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": "Logout failed"}), 500


@auth_bp.route("/me", methods=["GET"])
@requires_auth
def me():
    try:
        return jsonify({"user": session.get("user")})
    except Exception as e:
        return jsonify({"error": "Failed to retrieve user"}), 500
