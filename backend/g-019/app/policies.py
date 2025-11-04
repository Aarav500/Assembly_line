from datetime import datetime, timedelta
import json
from flask import jsonify
from . import db
from .models import TenantModelPolicy, TenantQuota, ModelRegistry, UsageLog

PERIODS = {
    'daily': timedelta(days=1),
    'monthly': timedelta(days=30),  # approximate month
}


def check_model_registered(model_name: str):
    return ModelRegistry.query.filter_by(name=model_name).first() is not None


def check_model_access(tenant_id: int, user_role: str, model_name: str):
    policy = TenantModelPolicy.query.filter_by(tenant_id=tenant_id, model_name=model_name).first()
    if policy is None:
        return False, {"reason": "no_policy", "message": "No policy found for model"}
    if not policy.allowed:
        return False, {"reason": "denied", "message": "Access to this model is denied"}
    roles_allowed = policy.roles_allowed()
    if roles_allowed and user_role not in roles_allowed:
        return False, {"reason": "role_not_allowed", "message": f"Role '{user_role}' not permitted for this model"}
    return True, None


def _reset_quota_window_if_needed(q: TenantQuota, now: datetime):
    period_delta = PERIODS.get(q.period)
    if not period_delta:
        return
    if q.window_start is None:
        q.window_start = now
        q.used_calls = 0
        return
    if now >= q.window_start + period_delta:
        q.window_start = now
        q.used_calls = 0


def _quota_status(q: TenantQuota, now: datetime):
    period_delta = PERIODS.get(q.period)
    resets_at = (q.window_start + period_delta) if (q.window_start and period_delta) else None
    remaining = max(q.max_calls - q.used_calls, 0)
    return {
        "period": q.period,
        "max_calls": q.max_calls,
        "used_calls": q.used_calls,
        "remaining": remaining,
        "resets_at": resets_at.isoformat() if resets_at else None,
    }


def enforce_and_consume_quota(tenant_id: int, user_id: int, model_name: str):
    now = datetime.utcnow()
    quotas = TenantQuota.query.filter_by(tenant_id=tenant_id).all()
    # If no quotas defined, allow unlimited by default
    if not quotas:
        log = UsageLog(tenant_id=tenant_id, user_id=user_id, model_name=model_name)
        db.session.add(log)
        db.session.commit()
        return True, None

    try:
        for q in quotas:
            _reset_quota_window_if_needed(q, now)
        db.session.flush()

        violations = []
        for q in quotas:
            if q.max_calls is not None and q.max_calls >= 0 and (q.used_calls + 1) > q.max_calls:
                violations.append(_quota_status(q, now))
        if violations:
            db.session.rollback()
            return False, {"error": "quota_exceeded", "violations": violations}

        for q in quotas:
            q.used_calls += 1
            db.session.add(q)
        log = UsageLog(tenant_id=tenant_id, user_id=user_id, model_name=model_name)
        db.session.add(log)
        db.session.commit()
        return True, None
    except Exception as e:
        db.session.rollback()
        return False, {"error": "quota_error", "message": str(e)}


def quotas_summary(tenant_id: int):
    now = datetime.utcnow()
    quotas = TenantQuota.query.filter_by(tenant_id=tenant_id).all()
    out = []
    for q in quotas:
        _reset_quota_window_if_needed(q, now)
        out.append(_quota_status(q, now))
    return out

