from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
import json

from .extensions import db
from .models import Environment, IdentityProvider, Role, RoleBinding, SessionCredential
from .jwt_utils import verify_id_token, issue_session_token, introspect_session_token, claims_match_requirement

api_bp = Blueprint("api", __name__)


def _error(message: str, status: int = 400):
    return jsonify({"error": message}), status


@api_bp.route("/environments", methods=["GET"])
def list_environments():
    envs = Environment.query.order_by(Environment.name.asc()).all()
    return jsonify([e.to_dict() for e in envs])


@api_bp.route("/environments", methods=["POST"])
def create_environment():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    description = data.get("description")
    if not name:
        return _error("name is required")
    env = Environment(name=name, description=description)
    try:
        db.session.add(env)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("environment with this name already exists", 409)
    return jsonify(env.to_dict()), 201


@api_bp.route("/providers", methods=["GET"])
def list_providers():
    providers = IdentityProvider.query.order_by(IdentityProvider.name.asc()).all()
    return jsonify([p.to_dict() for p in providers])


@api_bp.route("/providers", methods=["POST"])
def create_provider():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    issuer = (data.get("issuer") or "").strip()
    audience = (data.get("audience") or "").strip()
    algorithm = (data.get("algorithm") or "RS256").strip()
    jwks_uri = (data.get("jwks_uri") or None)
    jwks_json = data.get("jwks_json")
    enabled = bool(data.get("enabled", True))

    if not name or not issuer or not audience:
        return _error("name, issuer, and audience are required")

    if not jwks_uri and not jwks_json:
        return _error("either jwks_uri or jwks_json must be provided")

    if jwks_json is not None and not isinstance(jwks_json, str):
        try:
            jwks_json = json.dumps(jwks_json)
        except Exception:
            return _error("jwks_json must be a valid JSON object or string")

    prov = IdentityProvider(
        name=name,
        issuer=issuer,
        audience=audience,
        algorithm=algorithm,
        jwks_uri=jwks_uri,
        jwks_json=jwks_json,
        enabled=enabled,
    )
    try:
        db.session.add(prov)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("provider with this name already exists", 409)
    return jsonify(prov.to_dict()), 201


@api_bp.route("/roles", methods=["GET"])
def list_roles():
    roles = Role.query.order_by(Role.name.asc()).all()
    return jsonify([r.to_dict() for r in roles])


@api_bp.route("/roles", methods=["POST"])
def create_role():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    description = data.get("description")
    if not name:
        return _error("name is required")
    role = Role(name=name, description=description)
    try:
        db.session.add(role)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("role with this name already exists", 409)
    return jsonify(role.to_dict()), 201


@api_bp.route("/role-bindings", methods=["GET"])
def list_bindings():
    bindings = RoleBinding.query.all()
    return jsonify([b.to_dict() for b in bindings])


@api_bp.route("/role-bindings", methods=["POST"])
def create_binding():
    data = request.get_json(force=True, silent=True) or {}
    role_name = (data.get("role_name") or "").strip()
    provider_id = (data.get("provider_id") or "").strip()
    required_claim = (data.get("required_claim") or None)
    required_value = (data.get("required_value") or None)
    allowed_environments = data.get("allowed_environments") or []

    if not role_name or not provider_id:
        return _error("role_name and provider_id are required")

    role = Role.query.filter_by(name=role_name).first()
    if not role:
        return _error("role not found", 404)

    provider = IdentityProvider.query.get(provider_id)
    if not provider:
        return _error("provider not found", 404)

    b = RoleBinding(
        role_id=role.id,
        provider_id=provider.id,
        required_claim=required_claim,
        required_value=required_value,
    )
    b.set_allowed_environments(list({str(x) for x in allowed_environments}))

    try:
        db.session.add(b)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("binding for this role and provider already exists", 409)

    return jsonify(b.to_dict()), 201


@api_bp.route("/federate", methods=["POST"])
def federate():
    data = request.get_json(force=True, silent=True) or {}
    provider_id = (data.get("provider_id") or "").strip()
    id_token = (data.get("id_token") or "").strip()
    role_name = (data.get("role_name") or "").strip()
    environment = (data.get("environment") or "").strip()

    if not provider_id or not id_token or not role_name or not environment:
        return _error("provider_id, id_token, role_name, and environment are required")

    provider = IdentityProvider.query.get(provider_id)
    if not provider or not provider.enabled:
        return _error("provider not found or disabled", 404)

    role = Role.query.filter_by(name=role_name).first()
    if not role:
        return _error("role not found", 404)

    env = Environment.query.filter_by(name=environment).first()
    if not env:
        return _error("environment not found", 404)

    binding = RoleBinding.query.filter_by(role_id=role.id, provider_id=provider.id).first()
    if not binding:
        return _error("no binding exists for this role and provider", 403)

    if environment not in binding.allowed_environments():
        return _error("environment not allowed for this role via this provider", 403)

    try:
        payload = verify_id_token(id_token, provider)
    except Exception as e:
        return _error(f"invalid id_token: {str(e)}", 401)

    if not claims_match_requirement(payload, binding.required_claim, binding.required_value):
        return _error("id_token does not satisfy binding claim requirement", 403)

    sub = str(payload.get("sub"))
    issued = issue_session_token(sub=sub, role_name=role.name, environment_name=env.name)

    token = issued["token"]
    claims = issued["claims"]

    cred = SessionCredential(
        jti=claims["jti"],
        user_sub=sub,
        role_name=role.name,
        environment_name=env.name,
        provider_id=provider.id,
        issued_at=datetime.fromtimestamp(claims["iat"], tz=timezone.utc),
        expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc),
        token=token,
        status="active",
    )
    db.session.add(cred)
    db.session.commit()

    return jsonify({
        "access_token": token,
        "token_type": "bearer",
        "expires_in": int(claims["exp"] - claims["iat"]),
        "role": role.name,
        "environment": env.name,
        "subject": sub,
    }), 200


@api_bp.route("/introspect", methods=["GET"]) 
def introspect():
    token = request.args.get("token")
    if not token:
        return _error("token query parameter is required")
    try:
        claims = introspect_session_token(token)
    except Exception as e:
        return _error(f"invalid token: {str(e)}", 401)

    cred = SessionCredential.query.filter_by(jti=claims.get("jti")).first()
    status = cred.status if cred else "unknown"
    return jsonify({"active": True, "claims": claims, "status": status})


@api_bp.route("/credentials", methods=["GET"]) 
def list_credentials():
    creds = SessionCredential.query.order_by(SessionCredential.issued_at.desc()).limit(100).all()
    return jsonify([c.to_dict() for c in creds])


@api_bp.route("/seed", methods=["POST"]) 
def seed():
    body = request.get_json(force=True, silent=True) or {}
    # Environments
    envs = ["dev", "staging", "prod"]
    created_envs = []
    for name in envs:
        if not Environment.query.filter_by(name=name).first():
            e = Environment(name=name, description=f"{name} environment")
            db.session.add(e)
            created_envs.append(name)
    # Roles
    roles = ["viewer", "developer", "admin"]
    created_roles = []
    for name in roles:
        if not Role.query.filter_by(name=name).first():
            r = Role(name=name, description=f"{name} role")
            db.session.add(r)
            created_roles.append(name)
    db.session.commit()

    return jsonify({
        "environments_created": created_envs,
        "roles_created": created_roles,
        "note": "Create an identity provider and a role binding to enable federation."
    }), 201

