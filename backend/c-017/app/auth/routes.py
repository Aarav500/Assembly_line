import json
from flask import Blueprint, request, jsonify, current_app, url_for
from sqlalchemy.exc import IntegrityError
from authlib.integrations.flask_client import OAuthError

from ..extensions import db, oauth
from ..models import User, Role, OAuthAccount
from ..utils.passwords import hash_password, verify_password
from .jwt_utils import create_token, token_required, extract_token_from_request, decode_token, revoke_token

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password")
    name = data.get("name")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User(email=email, name=name, password_hash=hash_password(password))
    # Assign default role 'user' if exists
    default_role = db.session.query(Role).filter_by(name="user").one_or_none()
    if default_role:
        user.roles.append(default_role)

    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Email already registered"}), 400

    access_token = create_token(user, token_type="access")
    refresh_token = create_token(user, token_type="refresh")
    return jsonify({"user": user.to_dict(), "access_token": access_token, "refresh_token": refresh_token}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = db.session.query(User).filter_by(email=email).one_or_none()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        return jsonify({"error": "Invalid credentials"}), 401

    if not user.is_active:
        return jsonify({"error": "User is inactive"}), 403

    access_token = create_token(user, token_type="access")
    refresh_token = create_token(user, token_type="refresh")
    return jsonify({"user": user.to_dict(), "access_token": access_token, "refresh_token": refresh_token})


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    token = extract_token_from_request("refresh")
    if not token:
        return jsonify({"error": "Missing refresh token"}), 400
    try:
        payload = decode_token(token)
        if payload.get("typ") != "refresh":
            return jsonify({"error": "Invalid token type"}), 400
    except Exception as e:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    user = db.session.get(User, int(payload.get("sub"))) if payload.get("sub") else None
    if not user or not user.is_active:
        return jsonify({"error": "User not found or inactive"}), 401

    access_token = create_token(user, token_type="access")
    refresh_token = create_token(user, token_type="refresh")
    return jsonify({"access_token": access_token, "refresh_token": refresh_token})


@auth_bp.route("/logout", methods=["POST"])
@token_required
def logout():
    # Revoke current access token
    access = extract_token_from_request("access")
    if access:
        try:
            p = decode_token(access)
            revoke_token(p.get("jti"), token_type="access", user_id=int(p.get("sub")) if p.get("sub") else None)
        except Exception:
            pass
    # Optionally revoke provided refresh token
    refresh = extract_token_from_request("refresh")
    if refresh:
        try:
            p2 = decode_token(refresh)
            revoke_token(p2.get("jti"), token_type="refresh", user_id=int(p2.get("sub")) if p2.get("sub") else None)
        except Exception:
            pass
    return jsonify({"status": "logged_out"})


@auth_bp.route("/me", methods=["GET"])
@token_required
def me():
    from flask import g
    return jsonify({"user": g.current_user.to_dict()})


@auth_bp.route("/oauth/<provider>/login")
def oauth_login(provider: str):
    client = oauth.create_client(provider)
    if client is None:
        return jsonify({"error": f"Unknown provider: {provider}"}), 404

    redirect_uri = url_for("auth.oauth_callback", provider=provider, _external=True)
    return client.authorize_redirect(redirect_uri)


def _fetch_github_userinfo(token):
    # GitHub: fetch primary email and profile
    client = oauth.create_client("github")
    if not client:
        return None
    resp_user = client.get("user", token=token)
    profile = resp_user.json()

    email = None
    try:
        resp_emails = client.get("user/emails", token=token)
        emails = resp_emails.json()
        primary = next((e for e in emails if e.get("primary")), None)
        email = (primary or (emails[0] if emails else {})).get("email")
    except Exception:
        email = profile.get("email")

    return {
        "sub": str(profile.get("id")),
        "email": email,
        "name": profile.get("name") or profile.get("login"),
    }


def _fetch_oidc_userinfo(provider: str, token):
    client = oauth.create_client(provider)
    if not client:
        return None
    # Try OIDC userinfo endpoint
    try:
        info = client.userinfo(token=token)
        if info:
            return {"sub": info.get("sub"), "email": info.get("email"), "name": info.get("name") or info.get("preferred_username")}
    except Exception:
        pass
    # Fallback: parse ID Token if present
    try:
        idinfo = client.parse_id_token(token)
        if idinfo:
            return {"sub": idinfo.get("sub"), "email": idinfo.get("email"), "name": idinfo.get("name") or idinfo.get("preferred_username")}
    except Exception:
        pass
    return None


@auth_bp.route("/oauth/<provider>/callback")
def oauth_callback(provider: str):
    client = oauth.create_client(provider)
    if client is None:
        return jsonify({"error": f"Unknown provider: {provider}"}), 404

    try:
        token = client.authorize_access_token()
    except OAuthError as e:
        return jsonify({"error": f"OAuth error: {e.error}", "description": getattr(e, 'description', None)}), 400

    if provider == "github":
        info = _fetch_github_userinfo(token)
    else:
        info = _fetch_oidc_userinfo(provider, token)

    if not info or not info.get("email"):
        return jsonify({"error": "Failed to retrieve user info or email not provided"}), 400

    email = (info.get("email") or "").lower()
    provider_user_id = str(info.get("sub")) if info.get("sub") is not None else email

    # Find or create user
    user = db.session.query(User).filter_by(email=email).one_or_none()
    if not user:
        user = User(email=email, name=info.get("name"))
        # Assign default role 'user' if exists
        default_role = db.session.query(Role).filter_by(name="user").one_or_none()
        if default_role:
            user.roles.append(default_role)
        db.session.add(user)
        db.session.flush()

    # Link or update OAuth account
    acct = (
        db.session.query(OAuthAccount)
        .filter_by(provider=provider, provider_user_id=provider_user_id)
        .one_or_none()
    )
    if not acct:
        acct = OAuthAccount(
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            token=json.dumps(token),
            user=user,
        )
        db.session.add(acct)
    else:
        acct.token = json.dumps(token)
        acct.email = email
        acct.user = user

    db.session.commit()

    access_token = create_token(user, token_type="access")
    refresh_token = create_token(user, token_type="refresh")

    return jsonify({"user": user.to_dict(), "access_token": access_token, "refresh_token": refresh_token, "provider": provider})

