import uuid
from datetime import datetime, date

from extensions import db


def _uuid():
    return str(uuid.uuid4())


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Plan(db.Model, TimestampMixin):
    __tablename__ = 'plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    price_cents = db.Column(db.Integer, nullable=False, default=0)
    # JSON mapping: metric -> included units per billing cycle
    included_quotas = db.Column(db.JSON, nullable=False, default=dict)
    # JSON mapping: metric -> overage rate in cents per unit
    overage_rates = db.Column(db.JSON, nullable=False, default=dict)

    tenants = db.relationship('Tenant', back_populates='plan')


class Tenant(db.Model, TimestampMixin):
    __tablename__ = 'tenants'
    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=True)
    api_key = db.Column(db.String(128), unique=True, nullable=False)

    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=True)
    plan = db.relationship('Plan', back_populates='tenants')

    # Arbitrary per-tenant JSON configuration: {"features": {...}, "limits": {...}, "limit_behavior": "block|overage"}
    config = db.Column(db.JSON, nullable=False, default=dict)

    billing_cycle_anchor = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(db.String(32), default='active', nullable=False)

    usage_events = db.relationship('UsageEvent', back_populates='tenant', cascade='all, delete-orphan')
    invoices = db.relationship('Invoice', back_populates='tenant', cascade='all, delete-orphan')


class UsageEvent(db.Model, TimestampMixin):
    __tablename__ = 'usage_events'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False)
    metric = db.Column(db.String(64), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tenant = db.relationship('Tenant', back_populates='usage_events')


class Invoice(db.Model, TimestampMixin):
    __tablename__ = 'invoices'
    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(32), nullable=False, default='open')  # draft|open|paid|void
    subtotal_cents = db.Column(db.Integer, nullable=False, default=0)
    tax_cents = db.Column(db.Integer, nullable=False, default=0)
    total_cents = db.Column(db.Integer, nullable=False, default=0)
    currency = db.Column(db.String(8), default='USD', nullable=False)
    paid_at = db.Column(db.DateTime, nullable=True)

    tenant = db.relationship('Tenant', back_populates='invoices')
    items = db.relationship('InvoiceItem', back_populates='invoice', cascade='all, delete-orphan')


class InvoiceItem(db.Model, TimestampMixin):
    __tablename__ = 'invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.String(36), db.ForeignKey('invoices.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    metric = db.Column(db.String(64), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price_cents = db.Column(db.Integer, nullable=False, default=0)
    amount_cents = db.Column(db.Integer, nullable=False, default=0)

    invoice = db.relationship('Invoice', back_populates='items')

