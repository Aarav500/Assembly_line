from datetime import datetime
from functools import wraps

from flask import jsonify

from extensions import db
from models import UsageEvent
from tenancy import get_current_tenant
from utils import billing_period_containing


def get_plan_limits(tenant, metric: str) -> int:
    # Defaults from plan, then override by tenant.config.limits
    plan_limits = 0
    if tenant.plan and tenant.plan.included_quotas:
        plan_limits = int(tenant.plan.included_quotas.get(metric, 0))
    limits_override = (tenant.config or {}).get('limits', {})
    if metric in limits_override:
        try:
            return int(limits_override[metric])
        except Exception:
            return plan_limits
    return plan_limits


def get_limit_behavior(tenant) -> str:
    return (tenant.config or {}).get('limit_behavior', 'overage')  # 'block' or 'overage'


def aggregate_usage(tenant, metric: str | None, start: datetime, end: datetime) -> dict:
    q = UsageEvent.query.filter(UsageEvent.tenant_id == tenant.id, UsageEvent.timestamp >= start, UsageEvent.timestamp < end)
    if metric:
        q = q.filter(UsageEvent.metric == metric)
    rows = q.all()
    totals = {}
    for r in rows:
        totals[r.metric] = totals.get(r.metric, 0) + int(r.quantity)
    return totals


def record_usage(tenant, metric: str, quantity: int = 1):
    e = UsageEvent(tenant_id=tenant.id, metric=metric, quantity=quantity)
    db.session.add(e)


def require_quota(metric: str, cost: int = 1):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            tenant = get_current_tenant()
            if not tenant:
                return jsonify({"error": "tenant_not_found"}), 401
            now = datetime.utcnow()
            anchor_day = tenant.billing_cycle_anchor.day
            start, end = billing_period_containing(now, anchor_day)

            used_map = aggregate_usage(tenant, metric, start, end)
            used = int(used_map.get(metric, 0))
            allowed = get_plan_limits(tenant, metric)
            behavior = get_limit_behavior(tenant)

            if allowed and behavior == 'block' and used + cost > allowed:
                return jsonify({
                    "error": "quota_exceeded",
                    "metric": metric,
                    "used": used,
                    "allowed": allowed,
                    "cost": cost
                }), 429

            record_usage(tenant, metric, cost)
            db.session.commit()
            return f(*args, **kwargs)
        return wrapper
    return decorator

