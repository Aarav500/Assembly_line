from datetime import datetime

from flask import Blueprint, jsonify, request

from extensions import db
from models import Invoice, Tenant
from auth import require_admin, require_tenant
from tenancy import get_current_tenant
from billing import generate_invoice_for_last_completed_cycle

bp = Blueprint('billing', __name__)


@bp.post('/billing/invoices/run')
@require_admin
def run_billing():
    data = request.get_json(silent=True) or {}
    tenant_id = data.get('tenant_id') or request.args.get('tenant_id')
    created = []
    tenants_q = Tenant.query.filter(Tenant.status == 'active')
    if tenant_id:
        tenants_q = tenants_q.filter(Tenant.id == tenant_id)
    for t in tenants_q.all():
        inv = generate_invoice_for_last_completed_cycle(t)
        if inv:
            created.append(inv.id)
    return jsonify({'created_invoices': created})


@bp.get('/billing/invoices')
@require_tenant
def list_invoices():
    tenant = get_current_tenant()
    invoices = Invoice.query.filter_by(tenant_id=tenant.id).order_by(Invoice.created_at.desc()).all()
    return jsonify([
        {
            'id': i.id,
            'status': i.status,
            'period_start': i.period_start.isoformat(),
            'period_end': i.period_end.isoformat(),
            'subtotal_cents': i.subtotal_cents,
            'tax_cents': i.tax_cents,
            'total_cents': i.total_cents,
            'items': [
                {
                    'id': it.id,
                    'description': it.description,
                    'metric': it.metric,
                    'quantity': it.quantity,
                    'unit_price_cents': it.unit_price_cents,
                    'amount_cents': it.amount_cents,
                }
                for it in i.items
            ],
        }
        for i in invoices
    ])


@bp.post('/billing/invoices/<invoice_id>/pay')
@require_admin
def pay_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    invoice.status = 'paid'
    invoice.paid_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'id': invoice.id, 'status': invoice.status, 'paid_at': invoice.paid_at.isoformat()})

