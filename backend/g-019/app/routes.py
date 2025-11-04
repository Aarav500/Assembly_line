from flask import Blueprint, jsonify, request, g
from sqlalchemy.exc import IntegrityError
import json
from . import db
from .auth import require_api_key, generate_api_key
from .models import Tenant, User, ApiKey, ModelRegistry, TenantModelPolicy, TenantQuota
from .policies import check_model_access, check_model_registered, enforce_and_consume_quota, quotas_summary

bp = Blueprint('api', __name__)


@bp.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


# Admin endpoints
@bp.route('/admin/tenants', methods=['POST'])
def create_tenant():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get('name')
    if not name:
        return jsonify({"error": "bad_request", "message": "name is required"}), 400
    tenant = Tenant(name=name)
    db.session.add(tenant)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "conflict", "message": "Tenant name already exists"}), 409
    return jsonify({"tenant": tenant.to_dict()}), 201


@bp.route('/admin/users', methods=['POST'])
def create_user():
    data = request.get_json(force=True, silent=True) or {}
    email = data.get('email')
    role = data.get('role', 'member')
    tenant_id = data.get('tenant_id')
    if not email or not tenant_id:
        return jsonify({"error": "bad_request", "message": "email and tenant_id are required"}), 400
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({"error": "not_found", "message": "Tenant not found"}), 404
    user = User(email=email, role=role, tenant_id=tenant_id)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "conflict", "message": "User email already exists"}), 409

    # Create API key
    key = generate_api_key()
    api_key = ApiKey(key=key, user_id=user.id, tenant_id=tenant_id)
    db.session.add(api_key)
    db.session.commit()
    return jsonify({"user": user.to_dict(), "api_key": api_key.key}), 201


@bp.route('/admin/models', methods=['POST'])
def register_model():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get('name')
    if not name:
        return jsonify({"error": "bad_request", "message": "name is required"}), 400
    model = ModelRegistry(name=name)
    db.session.add(model)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "conflict", "message": "Model already registered"}), 409
    return jsonify({"model": model.to_dict()}), 201


@bp.route('/admin/policies', methods=['POST'])
def upsert_policy():
    data = request.get_json(force=True, silent=True) or {}
    tenant_id = data.get('tenant_id')
    model_name = data.get('model_name')
    allowed = data.get('allowed', True)
    roles_allowed = data.get('roles_allowed')  # list or None

    if not tenant_id or not model_name:
        return jsonify({"error": "bad_request", "message": "tenant_id and model_name are required"}), 400

    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({"error": "not_found", "message": "Tenant not found"}), 404

    if not check_model_registered(model_name):
        return jsonify({"error": "not_found", "message": "Model not registered"}), 404

    policy = TenantModelPolicy.query.filter_by(tenant_id=tenant_id, model_name=model_name).first()
    roles_json = json.dumps(roles_allowed) if roles_allowed is not None else None
    if policy:
        policy.allowed = bool(allowed)
        policy.roles_allowed_json = roles_json
    else:
        policy = TenantModelPolicy(
            tenant_id=tenant_id,
            model_name=model_name,
            allowed=bool(allowed),
            roles_allowed_json=roles_json,
        )
        db.session.add(policy)
    db.session.commit()
    return jsonify({"policy": policy.to_dict()}), 201


@bp.route('/admin/quotas', methods=['POST'])
def upsert_quota():
    data = request.get_json(force=True, silent=True) or {}
    tenant_id = data.get('tenant_id')
    period = data.get('period')  # 'daily' or 'monthly'
    max_calls = data.get('max_calls')
    reset = data.get('reset', False)

    if tenant_id is None or period not in ('daily', 'monthly') or max_calls is None:
        return jsonify({"error": "bad_request", "message": "tenant_id, period ('daily'|'monthly'), and max_calls are required"}), 400

    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({"error": "not_found", "message": "Tenant not found"}), 404

    quota = TenantQuota.query.filter_by(tenant_id=tenant_id, period=period).first()
    if quota:
        quota.max_calls = int(max_calls)
        if reset:
            from datetime import datetime
            quota.used_calls = 0
            quota.window_start = datetime.utcnow()
    else:
        quota = TenantQuota(tenant_id=tenant_id, period=period, max_calls=int(max_calls))
        db.session.add(quota)
    db.session.commit()
    return jsonify({"quota": quota.to_dict()}), 201


@bp.route('/admin/tenants/<int:tenant_id>/summary', methods=['GET'])
def tenant_summary(tenant_id):
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({"error": "not_found", "message": "Tenant not found"}), 404
    quotas = quotas_summary(tenant_id)
    policies = [p.to_dict() for p in tenant.model_policies]
    return jsonify({"tenant": tenant.to_dict(), "policies": policies, "quotas": quotas})


@bp.route('/admin/tenants/<int:tenant_id>/policies', methods=['GET'])
def list_policies(tenant_id):
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({"error": "not_found", "message": "Tenant not found"}), 404
    return jsonify({"policies": [p.to_dict() for p in tenant.model_policies]})


# Invocation endpoint (requires API key)
@bp.route('/invoke', methods=['POST'])
@require_api_key
def invoke_model():
    data = request.get_json(force=True, silent=True) or {}
    model = data.get('model')
    prompt = data.get('input')

    if not model or prompt is None:
        return jsonify({"error": "bad_request", "message": "model and input are required"}), 400

    # Check model registration
    if not check_model_registered(model):
        return jsonify({"error": "not_found", "message": "Model not registered"}), 404

    # Check access policy
    allowed, detail = check_model_access(g.tenant.id, g.user.role, model)
    if not allowed:
        return jsonify({"error": "forbidden", "detail": detail}), 403

    # Enforce quotas
    ok, qdetail = enforce_and_consume_quota(g.tenant.id, g.user.id, model)
    if not ok:
        status = 429 if qdetail and qdetail.get('error') == 'quota_exceeded' else 500
        return jsonify(qdetail or {"error": "quota_error"}), status

    # Simulate model response (echo service)
    output = f"[model={model}] {prompt}"

    return jsonify({
        "model": model,
        "input": prompt,
        "output": output,
        "meta": {
            "tenant_id": g.tenant.id,
            "user_id": g.user.id,
        }
    })

