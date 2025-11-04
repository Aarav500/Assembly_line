from datetime import datetime

from flask import Blueprint, jsonify, request

from extensions import db
from models import UsageEvent
from auth import require_tenant
from tenancy import get_current_tenant
from quotas import aggregate_usage
from utils import billing_period_containing

bp = Blueprint('usage', __name__)


@bp.post('/usage/report')
@require_tenant
def report_usage():
    tenant = get_current_tenant()
    data = request.get_json(silent=True) or {}
    metric = data.get('metric')
    quantity = int(data.get('quantity', 1) or 1)
    if not metric or quantity <= 0:
        return jsonify({"error": "invalid_metric_or_quantity"}), 400
    e = UsageEvent(tenant_id=tenant.id, metric=metric, quantity=quantity)
    db.session.add(e)
    db.session.commit()

    now = datetime.utcnow()
    start, end = billing_period_containing(now, tenant.billing_cycle_anchor.day)
    totals = aggregate_usage(tenant, metric, start, end)
    return jsonify({
        'ok': True,
        'metric': metric,
        'quantity': quantity,
        'period_start': start.isoformat(),
        'period_end': end.isoformat(),
        'used_in_period': int(totals.get(metric, 0)),
    })


@bp.get('/usage')
@require_tenant
def get_usage():
    tenant = get_current_tenant()
    metric = request.args.get('metric')
    now = datetime.utcnow()
    start, end = billing_period_containing(now, tenant.billing_cycle_anchor.day)
    totals = aggregate_usage(tenant, metric, start, end)
    return jsonify({
        'tenant_id': tenant.id,
        'period_start': start.isoformat(),
        'period_end': end.isoformat(),
        'totals': totals,
    })


@bp.post('/resource/action')
@require_tenant
def resource_action_example():
    # Example of metered endpoint: counts as one api_call unit
    from quotas import require_quota

    @require_quota('api_calls', 1)
    def _inner():
        return jsonify({'ok': True, 'message': 'action performed'})

    return _inner()

