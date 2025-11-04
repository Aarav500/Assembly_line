import os
import uuid
from flask import Blueprint, request, redirect, url_for, current_app, flash, jsonify
from flask_login import login_required, current_user
from models import db, Template, Purchase

payments_bp = Blueprint('payments', __name__)

try:
    import stripe
except Exception:  # pragma: no cover
    stripe = None


@payments_bp.route('/template/<int:template_id>/purchase', methods=['POST'])
@login_required
def purchase_template(template_id):
    tmpl = Template.query.get_or_404(template_id)
    if tmpl.owner_id == current_user.id:
        flash('You already own this template as the seller.', 'info')
        return redirect(url_for('marketplace.template_detail', template_id=template_id))

    existing = Purchase.query.filter_by(user_id=current_user.id, template_id=template_id).first()
    if existing and existing.status == 'paid':
        flash('You already purchased this template.', 'info')
        return redirect(url_for('marketplace.template_detail', template_id=template_id))

    stripe_secret = current_app.config.get('STRIPE_SECRET_KEY')
    base_url = current_app.config.get('BASE_URL')

    if stripe and stripe_secret:
        stripe.api_key = stripe_secret
        # Create or update pending purchase
        if not existing:
            purchase = Purchase(user_id=current_user.id, template_id=tmpl.id, amount_cents=tmpl.price_cents, currency=tmpl.currency, payment_provider='stripe', status='pending')
            db.session.add(purchase)
            db.session.commit()
        else:
            purchase = existing
            purchase.amount_cents = tmpl.price_cents
            purchase.currency = tmpl.currency
            purchase.payment_provider = 'stripe'
            purchase.status = 'pending'
            db.session.commit()
        try:
            session = stripe.checkout.Session.create(
                mode='payment',
                line_items=[{
                    'price_data': {
                        'currency': tmpl.currency,
                        'product_data': {'name': f"{tmpl.title} (Template)"},
                        'unit_amount': max(0, tmpl.price_cents),
                    },
                    'quantity': 1,
                }],
                success_url=f"{base_url}{url_for('payments.purchase_success')}?session_id={{CHECKOUT_SESSION_ID}}&t={tmpl.id}",
                cancel_url=f"{base_url}{url_for('marketplace.template_detail', template_id=tmpl.id)}",
                metadata={'purchase_id': str(purchase.id), 'template_id': str(tmpl.id), 'buyer_id': str(current_user.id)},
            )
            purchase.payment_id = session.id
            db.session.commit()
            return redirect(session.url)
        except Exception as e:
            current_app.logger.exception('Stripe Checkout error: %s', e)
            flash('Payment provider error. Using test checkout instead.', 'error')
            # fall back to test
    # Simulated payment (test mode)
    if not existing:
        purchase = Purchase(user_id=current_user.id, template_id=tmpl.id, amount_cents=tmpl.price_cents, currency=tmpl.currency, payment_provider='sim', payment_id=uuid.uuid4().hex, status='paid')
        db.session.add(purchase)
    else:
        purchase = existing
        purchase.amount_cents = tmpl.price_cents
        purchase.currency = tmpl.currency
        purchase.payment_provider = 'sim'
        purchase.payment_id = uuid.uuid4().hex
        purchase.status = 'paid'
    db.session.commit()
    flash('Purchase completed (simulated).', 'success')
    return redirect(url_for('marketplace.template_detail', template_id=tmpl.id))


@payments_bp.route('/purchase/success')
@login_required
def purchase_success():
    session_id = request.args.get('session_id')
    template_id = request.args.get('t')
    if not session_id or not template_id:
        return redirect(url_for('marketplace.index'))
    stripe_secret = current_app.config.get('STRIPE_SECRET_KEY')
    if not stripe or not stripe_secret:
        return redirect(url_for('marketplace.template_detail', template_id=template_id))
    stripe.api_key = stripe_secret
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        current_app.logger.exception('Stripe retrieve session error: %s', e)
        return redirect(url_for('marketplace.template_detail', template_id=template_id))
    purchase_id = session.metadata.get('purchase_id') if session.metadata else None
    if not purchase_id:
        return redirect(url_for('marketplace.template_detail', template_id=template_id))
    purchase = Purchase.query.get(purchase_id)
    if not purchase or purchase.user_id != current_user.id:
        return redirect(url_for('marketplace.template_detail', template_id=template_id))
    purchase.status = 'paid'
    db.session.commit()
    return redirect(url_for('marketplace.template_detail', template_id=purchase.template_id))


@payments_bp.route('/license/verify')
def license_verify():
    key = request.args.get('key', '').strip()
    template_id = request.args.get('template_id', '').strip()
    if not key or not template_id:
        return jsonify({'valid': False, 'reason': 'missing parameters'}), 400
    purchase = Purchase.query.filter_by(license_key=key, template_id=int(template_id), status='paid').first()
    if purchase:
        return jsonify({'valid': True, 'buyer_id': purchase.user_id, 'template_id': purchase.template_id, 'purchased_at': purchase.created_at.isoformat()})
    return jsonify({'valid': False}), 404


