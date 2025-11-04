from datetime import datetime

from extensions import db
from models import Invoice, InvoiceItem, UsageEvent
from utils import last_completed_billing_period


def compute_overage_for_period(tenant, start: datetime, end: datetime):
    # Aggregate usage by metric in period
    q = db.session.query(UsageEvent.metric, db.func.sum(UsageEvent.quantity)).filter(
        UsageEvent.tenant_id == tenant.id,
        UsageEvent.timestamp >= start,
        UsageEvent.timestamp < end,
    ).group_by(UsageEvent.metric)
    usage_map = {metric: int(total or 0) for metric, total in q}

    # Determine allowed quotas and overage rates from plan and tenant config
    included = {}
    rates = {}
    if tenant.plan:
        included.update(tenant.plan.included_quotas or {})
        rates.update(tenant.plan.overage_rates or {})
    # Tenant-specific overrides for limits only affect included quotas
    limits_override = (tenant.config or {}).get('limits', {})
    if limits_override:
        for k, v in limits_override.items():
            try:
                included[k] = int(v)
            except Exception:
                pass

    overages = []
    for metric, used in usage_map.items():
        allowed = int(included.get(metric, 0))
        if allowed < used:
            over_units = used - allowed
            unit_rate = int(rates.get(metric, 0))
            amount = over_units * unit_rate
            overages.append({
                'metric': metric,
                'used': used,
                'allowed': allowed,
                'over_units': over_units,
                'unit_rate_cents': unit_rate,
                'amount_cents': amount,
            })
    return overages


def invoice_exists_for_period(tenant, start: datetime, end: datetime) -> bool:
    return db.session.query(Invoice.id).filter(
        Invoice.tenant_id == tenant.id,
        Invoice.period_start == start,
        Invoice.period_end == end,
    ).first() is not None


def generate_invoice_for_last_completed_cycle(tenant) -> Invoice | None:
    now = datetime.utcnow()
    anchor_day = tenant.billing_cycle_anchor.day
    start, end = last_completed_billing_period(now, anchor_day)

    if invoice_exists_for_period(tenant, start, end):
        return None

    overages = compute_overage_for_period(tenant, start, end)

    invoice = Invoice(
        tenant_id=tenant.id,
        period_start=start,
        period_end=end,
        status='open',
        subtotal_cents=0,
        tax_cents=0,
        total_cents=0,
    )
    db.session.add(invoice)

    # Subscription base price
    base_price = int(getattr(tenant.plan, 'price_cents', 0) or 0)
    if base_price > 0:
        item = InvoiceItem(
            invoice=invoice,
            description=f"Subscription - {tenant.plan.name if tenant.plan else 'Plan'}",
            metric=None,
            quantity=1,
            unit_price_cents=base_price,
            amount_cents=base_price,
        )
        invoice.items.append(item)
        invoice.subtotal_cents += base_price

    # Overage items
    for ov in overages:
        if ov['amount_cents'] <= 0:
            continue
        desc = f"Overage for {ov['metric']} ({ov['over_units']} units @ {ov['unit_rate_cents']}c)"
        item = InvoiceItem(
            invoice=invoice,
            description=desc,
            metric=ov['metric'],
            quantity=ov['over_units'],
            unit_price_cents=ov['unit_rate_cents'],
            amount_cents=ov['amount_cents'],
        )
        invoice.items.append(item)
        invoice.subtotal_cents += ov['amount_cents']

    # Taxes could be applied here; for demo, 0
    invoice.total_cents = invoice.subtotal_cents + invoice.tax_cents

    db.session.commit()
    return invoice

