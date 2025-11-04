import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import logging
from datetime import timedelta
from flask import Flask, request, jsonify, render_template, redirect
from dotenv import load_dotenv
import stripe

load_dotenv()

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(seconds=0)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stripe-app")

# Stripe configuration
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
DOMAIN_URL = os.getenv('APP_DOMAIN', 'http://localhost:4242')

if not STRIPE_SECRET_KEY:
    logger.warning("STRIPE_SECRET_KEY not set. Please configure environment variables.")

stripe.api_key = STRIPE_SECRET_KEY


def _default_success_url():
    return f"{DOMAIN_URL}/success"


def _default_cancel_url():
    return f"{DOMAIN_URL}/cancel"


@app.get('/')
def index():
    return render_template('index.html', publishable_key=STRIPE_PUBLISHABLE_KEY, domain_url=DOMAIN_URL)


@app.get('/config')
def get_config():
    return jsonify({
        'publishableKey': STRIPE_PUBLISHABLE_KEY,
        'domain': DOMAIN_URL
    })


@app.post('/create-checkout-session')
def create_checkout_session():
    try:
        data = request.get_json(silent=True) or {}
        price_id = data.get('price_id')
        quantity = int(data.get('quantity', 1))
        customer_id = data.get('customer_id')
        customer_email = data.get('customer_email')
        metadata = data.get('metadata') or {}
        success_url = data.get('success_url') or _default_success_url()
        cancel_url = data.get('cancel_url') or _default_cancel_url()

        if not price_id:
            return jsonify({'error': 'price_id is required'}), 400

        params = {
            'mode': 'payment',
            'line_items': [{
                'price': price_id,
                'quantity': quantity
            }],
            'success_url': success_url + '?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': cancel_url,
            'allow_promotion_codes': True,
            'metadata': metadata,
            'automatic_tax': {'enabled': True}
        }

        # Create or attach customer
        if customer_id:
            params['customer'] = customer_id
        elif customer_email:
            params['customer_email'] = customer_email
        else:
            params['customer_creation'] = {'enabled': True}

        session = stripe.checkout.Session.create(**params)
        return jsonify({'id': session.get('id'), 'url': session.get('url')})
    except stripe.error.StripeError as e:
        logger.exception('Stripe error in create-checkout-session')
        return jsonify({'error': str(e.user_message or str(e))}), 400
    except Exception as e:
        logger.exception('Server error in create-checkout-session')
        return jsonify({'error': str(e)}), 500


@app.post('/create-subscription-session')
def create_subscription_session():
    try:
        data = request.get_json(silent=True) or {}
        price_id = data.get('price_id')
        quantity = int(data.get('quantity', 1))
        trial_days = data.get('trial_period_days')
        customer_id = data.get('customer_id')
        customer_email = data.get('customer_email')
        metadata = data.get('metadata') or {}
        success_url = data.get('success_url') or _default_success_url()
        cancel_url = data.get('cancel_url') or _default_cancel_url()

        if not price_id:
            return jsonify({'error': 'price_id is required'}), 400

        subscription_data = {'metadata': metadata}
        if trial_days is not None:
            subscription_data['trial_period_days'] = int(trial_days)

        params = {
            'mode': 'subscription',
            'line_items': [{
                'price': price_id,
                'quantity': quantity
            }],
            'subscription_data': subscription_data,
            'success_url': success_url + '?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': cancel_url,
            'allow_promotion_codes': True,
            'automatic_tax': {'enabled': True}
        }

        # Customer handling
        if customer_id:
            params['customer'] = customer_id
        elif customer_email:
            params['customer_email'] = customer_email
        else:
            params['customer_creation'] = {'enabled': True}

        session = stripe.checkout.Session.create(**params)
        return jsonify({'id': session.get('id'), 'url': session.get('url')})
    except stripe.error.StripeError as e:
        logger.exception('Stripe error in create-subscription-session')
        return jsonify({'error': str(e.user_message or str(e))}), 400
    except Exception as e:
        logger.exception('Server error in create-subscription-session')
        return jsonify({'error': str(e)}), 500


@app.post('/create-portal-session')
def create_portal_session():
    try:
        data = request.get_json(silent=True) or {}
        customer_id = data.get('customer_id')
        return_url = data.get('return_url') or DOMAIN_URL

        if not customer_id:
            return jsonify({'error': 'customer_id is required'}), 400

        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url
        )
        return jsonify({'url': portal_session.url})
    except stripe.error.StripeError as e:
        logger.exception('Stripe error in create-portal-session')
        return jsonify({'error': str(e.user_message or str(e))}), 400
    except Exception as e:
        logger.exception('Server error in create-portal-session')
        return jsonify({'error': str(e)}), 500


@app.post('/invoices/create')
def create_invoice():
    try:
        data = request.get_json(silent=True) or {}
        customer_id = data.get('customer_id')
        if not customer_id:
            return jsonify({'error': 'customer_id is required'}), 400

        items = data.get('items') or []
        if not items:
            return jsonify({'error': 'items must be a non-empty list'}), 400

        collection_method = data.get('collection_method', 'charge_automatically')
        days_until_due = data.get('days_until_due')
        currency = data.get('currency', 'usd')
        auto_advance = data.get('auto_advance', True)
        send_invoice = data.get('send_invoice', False)
        description = data.get('description')
        metadata = data.get('metadata') or {}

        # Create invoice items
        created_items = []
        for item in items:
            if 'price_id' in item:
                ii = stripe.InvoiceItem.create(
                    customer=customer_id,
                    price=item['price_id'],
                    quantity=int(item.get('quantity', 1)),
                )
            else:
                amount = item.get('amount')
                if amount is None:
                    return jsonify({'error': 'Each item must have price_id or amount'}), 400
                ii = stripe.InvoiceItem.create(
                    customer=customer_id,
                    amount=int(amount),
                    currency=item.get('currency', currency),
                    description=item.get('description')
                )
            created_items.append(ii.id)

        invoice_params = {
            'customer': customer_id,
            'collection_method': collection_method,
            'auto_advance': auto_advance,
            'metadata': metadata
        }
        if days_until_due is not None and collection_method == 'send_invoice':
            invoice_params['days_until_due'] = int(days_until_due)
        if description:
            invoice_params['description'] = description

        invoice = stripe.Invoice.create(**invoice_params)

        # Finalize and send if requested
        if collection_method == 'send_invoice':
            stripe.Invoice.finalize_invoice(invoice.id)
            if send_invoice:
                stripe.Invoice.send_invoice(invoice.id)
        else:
            # charge_automatically: finalize to attempt immediate payment
            invoice = stripe.Invoice.finalize_invoice(invoice.id)

        return jsonify({'invoice_id': invoice.id, 'status': invoice.status, 'hosted_invoice_url': invoice.hosted_invoice_url})
    except stripe.error.StripeError as e:
        logger.exception('Stripe error in create-invoice')
        return jsonify({'error': str(e.user_message or str(e))}), 400
    except Exception as e:
        logger.exception('Server error in create-invoice')
        return jsonify({'error': str(e)}), 500


@app.post('/refunds')
def create_refund():
    try:
        data = request.get_json(silent=True) or {}
        payment_intent_id = data.get('payment_intent_id')
        charge_id = data.get('charge_id')
        amount = data.get('amount')
        reason = data.get('reason')

        params = {}
        if payment_intent_id:
            params['payment_intent'] = payment_intent_id
        elif charge_id:
            params['charge'] = charge_id
        else:
            return jsonify({'error': 'payment_intent_id or charge_id is required'}), 400

        if amount is not None:
            params['amount'] = int(amount)
        if reason:
            params['reason'] = reason

        refund = stripe.Refund.create(**params)
        return jsonify({'refund_id': refund.id, 'status': refund.status})
    except stripe.error.StripeError as e:
        logger.exception('Stripe error in create-refund')
        return jsonify({'error': str(e.user_message or str(e))}), 400
    except Exception as e:
        logger.exception('Server error in create-refund')
        return jsonify({'error': str(e)}), 500


@app.post('/webhook')
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', '')

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=STRIPE_WEBHOOK_SECRET
            )
        else:
            # Insecure: For local testing without a secret only
            event = json.loads(payload)
    except ValueError as e:
        logger.warning('Invalid payload')
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        logger.warning('Invalid signature')
        return jsonify({'error': 'Invalid signature'}), 400

    event_type = event['type']
    data_object = event['data']['object']

    logger.info(f"Webhook received: {event_type}")

    try:
        if event_type == 'checkout.session.completed':
            session = data_object
            mode = session.get('mode')
            customer = session.get('customer')
            if mode == 'subscription':
                subscription_id = session.get('subscription')
                logger.info(f"Subscription created: {subscription_id} for customer {customer}")
            elif mode == 'payment':
                payment_intent_id = session.get('payment_intent')
                logger.info(f"Payment completed: {payment_intent_id} for customer {customer}")
        elif event_type == 'invoice.finalized':
            logger.info(f"Invoice finalized: {data_object.get('id')}")
        elif event_type == 'invoice.paid':
            logger.info(f"Invoice paid: {data_object.get('id')}")
        elif event_type == 'invoice.payment_failed':
            logger.warning(f"Invoice payment failed: {data_object.get('id')}")
        elif event_type == 'customer.subscription.created':
            logger.info(f"Subscription created: {data_object.get('id')}")
        elif event_type == 'customer.subscription.updated':
            logger.info(f"Subscription updated: {data_object.get('id')} status={data_object.get('status')}")
        elif event_type == 'customer.subscription.deleted':
            logger.info(f"Subscription deleted: {data_object.get('id')}")
        elif event_type == 'payment_intent.succeeded':
            logger.info(f"PaymentIntent succeeded: {data_object.get('id')}")
        elif event_type == 'charge.refunded':
            logger.info(f"Charge refunded: {data_object.get('id')}")
        else:
            logger.debug(f"Unhandled event type: {event_type}")
    except Exception:
        logger.exception('Error processing webhook event')
        return jsonify({'status': 'error'}), 500

    return jsonify({'status': 'success'})


@app.get('/success')
def success():
    return render_template('success.html')


@app.get('/cancel')
def cancel():
    return render_template('cancel.html')


if __name__ == '__main__':
    port = int(os.getenv('PORT', '4242'))
    app.run(host='0.0.0.0', port=port, debug=True)



def create_app():
    return app
