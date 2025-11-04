import secrets
from datetime import date

from flask import Blueprint, jsonify, request

from extensions import db
from models import Plan, Tenant
from auth import require_admin

bp = Blueprint('tenants', __name__)


@bp.get('/plans')
def list_plans():
    plans = Plan.query.order_by(Plan.id).all()
    return jsonify([
        {
            'id': p.id,
            'name': p.name,
            'price_cents': p.price_cents,
            'included_quotas': p.included_quotas,
            'overage_rates': p.overage_rates,
        }
        for p in plans
    ])


@bp.post('/tenants')
@require_admin
def create_tenant():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    plan_id = data.get('plan_id')
    slug = data.get('slug')
    config = data.get('config') or {}
    if not name:
        return jsonify({"error": "name_required"}), 400

    plan = Plan.query.get(plan_id) if plan_id else None

    api_key = secrets.token_hex(24)
    tenant = Tenant(
        name=name,
        slug=slug,
        api_key=api_key,
        plan=plan,
        config=config,
        billing_cycle_anchor=data.get('billing_cycle_anchor') or date.today(),
    )
    db.session.add(tenant)
    db.session.commit()
    return jsonify({
        'id': tenant.id,
        'name': tenant.name,
        'slug': tenant.slug,
        'api_key': tenant.api_key,
        'plan_id': tenant.plan_id,
        'config': tenant.config,
        'billing_cycle_anchor': str(tenant.billing_cycle_anchor),
        'status': tenant.status,
    }), 201


@bp.get('/tenants/<tenant_id>')
@require_admin
def get_tenant_admin(tenant_id):
    tenant = Tenant.query.get_or_404(tenant_id)
    return jsonify({
        'id': tenant.id,
        'name': tenant.name,
        'slug': tenant.slug,
        'plan_id': tenant.plan_id,
        'config': tenant.config,
        'billing_cycle_anchor': str(tenant.billing_cycle_anchor),
        'status': tenant.status,
        'created_at': tenant.created_at.isoformat(),
    })


@bp.patch('/tenants/<tenant_id>/config')
@require_admin
def update_tenant_config(tenant_id):
    tenant = Tenant.query.get_or_404(tenant_id)
    data = request.get_json(silent=True) or {}
    existing = tenant.config or {}
    # Shallow merge for simplicity
    existing.update(data)
    tenant.config = existing
    db.session.commit()
    return jsonify({'id': tenant.id, 'config': tenant.config})


@bp.post('/tenants/<tenant_id>/rotate-key')
@require_admin
def rotate_tenant_key(tenant_id):
    tenant = Tenant.query.get_or_404(tenant_id)
    tenant.api_key = secrets.token_hex(24)
    db.session.commit()
    return jsonify({'id': tenant.id, 'api_key': tenant.api_key})


@bp.patch('/tenants/<tenant_id>')
@require_admin
def update_tenant(tenant_id):
    tenant = Tenant.query.get_or_404(tenant_id)
    data = request.get_json(silent=True) or {}
    if 'name' in data:
        tenant.name = data['name']
    if 'slug' in data:
        tenant.slug = data['slug']
    if 'status' in data:
        tenant.status = data['status']
    if 'plan_id' in data:
        tenant.plan_id = data['plan_id']
    db.session.commit()
    return jsonify({'id': tenant.id, 'name': tenant.name, 'slug': tenant.slug, 'status': tenant.status, 'plan_id': tenant.plan_id})

