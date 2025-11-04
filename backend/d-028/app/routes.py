import hashlib
import hmac
import json
import logging
from flask import Blueprint, current_app, request, abort
from .service import process_github_event


webhook_bp = Blueprint("webhook", __name__)


def verify_signature(secret: str, body: bytes, signature_header: str) -> bool:
    if not secret:
        return True
    if not signature_header:
        return False
    try:
        sha_name, signature = signature_header.split("=", 1)
    except ValueError:
        return False
    if sha_name != "sha256":
        return False
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    expected = mac.hexdigest()
    # Use hmac.compare_digest for timing-safe compare
    return hmac.compare_digest(expected, signature)


@webhook_bp.route("/github", methods=["POST"]) 
def github_webhook():
    body = request.get_data()
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(current_app.config.get("GITHUB_WEBHOOK_SECRET", ""), body, sig):
        abort(401, description="Invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    delivery = request.headers.get("X-GitHub-Delivery", "")
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        abort(400, description="Invalid JSON payload")

    logging.info("Received GitHub event %s delivery %s", event, delivery)

    try:
        result = process_github_event(payload, event)
    except Exception as e:
        logging.exception("Error processing event: %s", e)
        abort(500, description=str(e))

    return result, 200

