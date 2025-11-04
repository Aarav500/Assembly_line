import logging
import os
from typing import Any, Dict, Optional

from flask import Blueprint, current_app, jsonify, request

try:
    import stripe
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "Stripe SDK is required. Ensure it is installed via requirements.txt"
    ) from exc


stripe_bp = Blueprint("stripe", __name__, url_prefix="/api")


def _init_stripe():
    secret_key = current_app.config.get("STRIPE_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured")
    stripe.api_key = secret_key


@stripe_bp.post("/stripe/create-checkout-session")
def create_checkout_session():
    """Create a Stripe Checkout Session.

    Request JSON can include either:
    - price_id (recommended) and optional quantity
    - OR amount (in smallest currency unit) and currency (e.g., 'usd')

    Additional recommended fields:
    - success_url (required)
    - cancel_url (required)
    - customer_email (optional)
    """
    _init_stripe()

    payload = request.get_json(silent=True) or {}

    success_url = payload.get("success_url")
    cancel_url = payload.get("cancel_url")

    if not success_url or not cancel_url:
        return jsonify({"error": "success_url and cancel_url are required"}), 400

    line_items = []

    price_id = payload.get("price_id")
    quantity = int(payload.get("quantity", 1))

    if price_id:
        line_items.append({"price": price_id, "quantity": quantity})
    else:
        amount = payload.get("amount")
        currency = (payload.get("currency") or "usd").lower()
        name = payload.get("name") or "Custom Payment"
        if amount is None:
            return jsonify({"error": "Either price_id or amount+currency is required"}), 400
        try:
            unit_amount = int(amount)
        except Exception:
            return jsonify({"error": "amount must be an integer (smallest currency unit)"}), 400
        if unit_amount <= 0:
            return jsonify({"error": "amount must be > 0"}), 400

        line_items.append(
            {
                "price_data": {
                    "currency": currency,
                    "unit_amount": unit_amount,
                    "product_data": {"name": name},
                },
                "quantity": quantity,
            }
        )

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            customer_email=payload.get("customer_email"),
            automatic_tax={"enabled": False},
        )
        return jsonify({"id": session.id, "url": session.url})
    except Exception as e:  # pragma: no cover
        logging.exception("Stripe create checkout session failed")
        return jsonify({"error": str(e)}), 400


@stripe_bp.post("/webhooks/stripe")
def stripe_webhook():
    """Handle Stripe webhooks with signature verification."""
    _init_stripe()

    endpoint_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")
    if not endpoint_secret:
        # Strongly recommended to configure a webhook secret.
        return jsonify({"error": "STRIPE_WEBHOOK_SECRET is not configured"}), 400

    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    if not sig_header:
        return jsonify({"error": "Missing Stripe-Signature header"}), 400

    try:
        event = stripe.Webhook.construct_event(
            payload=payload, sig_header=sig_header, secret=endpoint_secret
        )
    except stripe.error.SignatureVerificationError as e:
        logging.warning("Stripe signature verification failed: %s", e)
        return jsonify({"error": "signature_verification_failed"}), 400
    except Exception as e:  # pragma: no cover
        logging.exception("Stripe webhook error")
        return jsonify({"error": str(e)}), 400

    # Handle event types you care about
    try:
        etype = event.get("type")
        data = event.get("data", {}).get("object", {})

        if etype == "checkout.session.completed":
            session_id = data.get("id")
            logging.info("Stripe checkout session completed: %s", session_id)
            # TODO: fulfill order, provision service, etc.
        elif etype == "payment_intent.succeeded":
            payment_intent = data.get("id")
            amount = data.get("amount")
            currency = data.get("currency")
            logging.info(
                "PaymentIntent succeeded: %s amount=%s %s", payment_intent, amount, currency
            )
        elif etype == "payment_intent.payment_failed":
            logging.warning("PaymentIntent failed: %s", data.get("id"))
        else:
            logging.debug("Unhandled Stripe event type: %s", etype)
    except Exception:
        logging.exception("Error processing Stripe event")
        return jsonify({"status": "error"}), 500

    return jsonify({"received": True})

