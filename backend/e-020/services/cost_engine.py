from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from flask import current_app
from sqlalchemy import and_
from database import db
from models import Resource, ResourceTag, CostRecord


DEFAULT_BASE_RATES = {
    'vm': 0.05,       # USD/hour
    'db': 0.12,
    'storage': 0.01,
    'cache': 0.03,
}

SIZE_MULTIPLIER = {
    'nano': 0.25,
    'micro': 0.5,
    'small': 1.0,
    'medium': 1.5,
    'large': 2.0,
    'xlarge': 3.0,
}

ENV_MULTIPLIER = {
    'prod': 1.2,
    'production': 1.2,
    'staging': 1.0,
    'dev': 0.8,
    'development': 0.8,
}

PRIORITY_MULTIPLIER = {
    'high': 1.1,
    'normal': 1.0,
    'low': 0.9,
}


def hour_start(dt: Optional[datetime] = None) -> datetime:
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.replace(minute=0, second=0, microsecond=0)


def prev_full_hour_start(dt: Optional[datetime] = None) -> datetime:
    hs = hour_start(dt)
    return hs - timedelta(hours=1)


def compute_resource_hourly_cost(resource: Resource, currency: Optional[str] = None) -> float:
    base = resource.base_rate if resource.base_rate is not None else DEFAULT_BASE_RATES.get(resource.type, 0.02)
    size_mult = SIZE_MULTIPLIER.get((resource.size or '').lower(), 1.0)
    tags = {t.key.lower(): (t.value.lower() if isinstance(t.value, str) else t.value) for t in resource.tags}

    env_mult = ENV_MULTIPLIER.get(tags.get('env') or tags.get('environment') or '', 1.0)
    prio_mult = PRIORITY_MULTIPLIER.get(tags.get('priority') or '', 1.0)

    # Example flat surcharge if missing cost-center tagging to incentivize proper tagging
    surcharge = 0.0
    if 'cost-center' not in tags and 'cost_center' not in tags:
        surcharge += 0.005

    amount = base * size_mult * env_mult * prio_mult + surcharge
    return float(amount)


def accrue_for_window(start_hour: datetime, end_hour: datetime, resource_id: Optional[int] = None) -> Dict:
    if start_hour.tzinfo is None:
        start_hour = start_hour.replace(tzinfo=timezone.utc)
    if end_hour.tzinfo is None:
        end_hour = end_hour.replace(tzinfo=timezone.utc)
    if end_hour <= start_hour:
        return {'created': 0, 'skipped': 0, 'from': start_hour.isoformat(), 'to': end_hour.isoformat()}

    currency = current_app.config.get('COST_CURRENCY', 'USD')
    created = 0
    skipped = 0

    q = Resource.query.filter_by(active=True)
    if resource_id:
        q = q.filter(Resource.id == resource_id)

    resources = q.all()
    if not resources:
        return {'created': 0, 'skipped': 0, 'from': start_hour.isoformat(), 'to': end_hour.isoformat()}

    hour = start_hour
    while hour < end_hour:
        for r in resources:
            # idempotency: skip if exists
            exists = CostRecord.query.filter_by(resource_id=r.id, start_hour=hour).first()
            if exists:
                skipped += 1
                continue
            amount = compute_resource_hourly_cost(r, currency)
            rec = CostRecord(
                resource_id=r.id,
                project_id=r.project_id,
                tenant_id=r.tenant_id,
                start_hour=hour,
                hours=1,
                amount=amount,
                currency=currency,
            )
            db.session.add(rec)
            created += 1
        hour += timedelta(hours=1)
    db.session.commit()
    return {'created': created, 'skipped': skipped, 'from': start_hour.isoformat(), 'to': end_hour.isoformat()}


def accrue_last_full_hour() -> Dict:
    end = hour_start()
    start = end - timedelta(hours=1)
    return accrue_for_window(start, end)

