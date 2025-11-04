import json
import logging
from typing import Any, Dict, Optional

import requests
from flask import Blueprint, current_app, jsonify, request

paypal_bp = Blueprint("paypal", __name__, url_prefix="/api")


def _paypal_base() -> str:
    base = current_app.config.get("PAYPAL_API_BASE")
    if callable(base):  # if Config property-like
        base = current_app.config.PAYPAL_API_BASE
    return base


def _paypal_credentials() -> Dict[str, str]:
    cid = current_app.config.get("PAYPAL_CLIENT_ID")
    secret = current_app.config.get("PAYPAL_CLIENT_SECRET")
    if not cid or not secret:
        raise RuntimeError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET are required")
    return {"client_id": cid, "client_secret": secret}


def _paypal_access_token() -> str:
    creds = _paypal_credentials()
    url = f"{_paypal_base()}/v1/oauth2/token"
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en_US",
    }

    resp = requests.post(
        url,
        headers=headers,
        data={"grant_type": "client_credentials"},
        auth=(creds["client_id"], creds["client_secret"]),
        timeout=15,
    )
    if not resp.ok:
        logging.error("PayPal token failure: %s %s", resp.status_code, resp.text)
        raise RuntimeError("Failed to obtain PayPal access token")
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("PayPal access token missing in response")
    return token


@paypal_bp.post("/paypal/create-order")
def paypal_create_order():
    """Create a PayPal order (intent: CAPTURE).

    Request JSON:
    - amount: string or numeric, e.g., "10.00"
    - currency: e.g., "USD" (default: USD)
    - return_url: URL user is redirected to after approval
    - cancel_url: URL user is redirected to if they cancel
    """
    payload = request.get_json(silent=True) or {}

    amount = payload.get("amount")
    currency = (payload.get("currency") or "USD").upper()
    return_url = payload.get("return_url")
    cancel_url = payload.get("cancel_url")

    if amount is None:
        return jsonify({"error": "amount is required"}), 400
    if not return_url or not cancel_url:
        return jsonify({"error": "return_url and cancel_url are required"}), 400

    token = _paypal_access_token()

    url = f"{_paypal_base()}/v2/checkout/orders"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "amount": {
                    "currency_code": currency,
                    "value": str(amount),
                }
            }
        ],
        "application_context": {
            "return_url": return_url,
            "cancel_url": cancel_url,
            "user_action": "PAY_NOW",
            "shipping_preference": "NO_SHIPPING",
        },
    }

    resp = requests.post(url, headers=headers, json=body, timeout=20)
    if not resp.ok:
        logging.error("PayPal create order error: %s %s", resp.status_code, resp.text)
        return jsonify({"error": "paypal_create_order_failed", "details": resp.text}), 400

    data = resp.json()
    order_id = data.get("id")
    approve_url = None
    for link in data.get("links", []):
        if link.get("rel") == "approve":
            approve_url = link.get("href")
            break

    return jsonify({"id": order_id, "approve_url": approve_url, "raw": data})


@paypal_bp.post("/paypal/capture-order")
def paypal_capture_order():
    """Capture an approved PayPal order.

    Request JSON:
    - order_id: the ID from create-order response or JS SDK
    """
    payload = request.get_json(silent=True) or {}
    order_id = payload.get("order_id")
    if not order_id:
        return jsonify({"error": "order_id is required"}), 400

    token = _paypal_access_token()

    url = f"{_paypal_base()}/v2/checkout/orders/{order_id}/capture"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = requests.post(url, headers=headers, json={}, timeout=20)
    if not resp.ok:
        logging.error("PayPal capture order error: %s %s", resp.status_code, resp.text)
        return jsonify({"error": "paypal_capture_failed", "details": resp.text}), 400

    return jsonify(resp.json())


@paypal_bp.post("/webhooks/paypal")
def paypal_webhook():
    """Handle PayPal webhooks. Verifies signature via PayPal API.

    Requires PAYPAL_WEBHOOK_ID configured.
    """
    webhook_id = current_app.config.get("PAYPAL_WEBHOOK_ID")
    if not webhook_id:
        return jsonify({"error": "PAYPAL_WEBHOOK_ID is not configured"}), 400

    body_text = request.get_data(as_text=True)
    try:
        body_json = json.loads(body_text or "{}")
    except Exception:
        return jsonify({"error": "invalid_json"}), 400

    transmission_id = request.headers.get("Paypal-Transmission-Id")
    transmission_time = request.headers.get("Paypal-Transmission-Time")
    cert_url = request.headers.get("Paypal-Cert-Url")
    auth_algo = request.headers.get("Paypal-Auth-Algo")
    transmission_sig = request.headers.get("Paypal-Transmission-Sig")

    if not all([transmission_id, transmission_time, cert_url, auth_algo, transmission_sig]):
        return jsonify({"error": "missing_paypal_verification_headers"}), 400

    token = _paypal_access_token()

    url = f"{_paypal_base()}/v1/notifications/verify-webhook-signature"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    verify_body = {
        "transmission_id": transmission_id,
        "transmission_time": transmission_time,
        "cert_url": cert_url,
        "auth_algo": auth_algo,
        "transmission_sig": transmission_sig,
        "webhook_id": webhook_id,
        "webhook_event": body_json,
    }

    vresp = requests.post(url, headers=headers, json=verify_body, timeout=20)

    if not vresp.ok:
        logging.error("PayPal webhook verify failed: %s %s", vresp.status_code, vresp.text)
        return jsonify({"error": "paypal_webhook_verify_failed"}), 400

    vdata = vresp.json()
    status = vdata.get("verification_status")
    if status != "VERIFIED":
        logging.warning("PayPal webhook invalid signature: %s", status)
        return jsonify({"error": "invalid_signature"}), 400

    # Process event
    try:
        etype = body_json.get("event_type")
        resource = body_json.get("resource", {})

        if etype == "CHECKOUT.ORDER.APPROVED":
            logging.info("PayPal order approved: %s", resource.get("id"))
            # You might capture here server-side if not done client-side.
        elif etype == "PAYMENT.CAPTURE.COMPLETED":
            amount = resource.get("amount", {})
            logging.info(
                "PayPal capture completed: %s %s",
                amount.get("value"),
                amount.get("currency_code"),
            )
            # TODO: fulfill order, mark as paid, etc.
        else:
            logging.debug("Unhandled PayPal event: %s", etype)
    except Exception:
        logging.exception("Error processing PayPal webhook")
        return jsonify({"status": "error"}), 500

    return jsonify({"received": True})

