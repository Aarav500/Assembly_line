import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import re
import uuid
from functools import wraps
from typing import Any, Dict

from flask import Flask, jsonify, request, abort

import email_queue
from email_queue import enqueue_message, get_message, get_logs, mark_bounce_or_complaint
from config import WEBHOOK_SECRET

app = Flask(__name__)


def _json():
    if not request.is_json:
        abort(400, description="Expected application/json")
    try:
        return request.get_json(force=True)
    except Exception:
        abort(400, description="Invalid JSON body")


_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def validate_email(addr: str) -> bool:
    return bool(addr and _EMAIL_RE.match(addr))


def require_webhook_secret(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if WEBHOOK_SECRET:
            auth = request.headers.get("X-Webhook-Secret")
            if auth != WEBHOOK_SECRET:
                abort(401, description="Unauthorized")
        return f(*args, **kwargs)
    return wrapper


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/send", methods=["POST"])
def send_email():
    data = _json()
    to_email = data.get("to")
    subject = data.get("subject")
    template_name = data.get("template")
    template_vars = data.get("data") or {}
    max_retries = data.get("max_retries")

    if not to_email or not validate_email(to_email):
        abort(400, description="Invalid or missing 'to' email")
    if not subject:
        abort(400, description="Missing 'subject'")
    if not template_name:
        abort(400, description="Missing 'template'")
    if max_retries is not None:
        try:
            max_retries = int(max_retries)
            if max_retries < 0:
                raise ValueError
        except Exception:
            abort(400, description="Invalid 'max_retries'")

    message_id = data.get("message_id") or str(uuid.uuid4())

    try:
        msg_pk = enqueue_message(
            to_email=to_email,
            subject=subject,
            template_name=template_name,
            template_vars=template_vars,
            message_id=message_id,
            max_retries=max_retries,
        )
    except Exception as e:
        abort(500, description=f"Failed to enqueue message: {e}")

    return jsonify({
        "id": msg_pk,
        "message_id": message_id,
        "status": "queued"
    }), 202


@app.route("/status/<int:msg_pk>", methods=["GET"])
def status(msg_pk: int):
    row = get_message(msg_pk)
    if not row:
        abort(404, description="Message not found")
    try:
        data = {
            "id": row["id"],
            "to": row["to_email"],
            "subject": row["subject"],
            "template": row["template_name"],
            "data": json.loads(row["template_vars"]) if row["template_vars"] else {},
            "status": row["status"],
            "last_error": row["last_error"],
            "retries": row["retries"],
            "max_retries": row["max_retries"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "sent_at": row["sent_at"],
            "message_id": row["message_id"],
            "smtp_message_id": row["smtp_message_id"],
            "provider": row["provider"],
            "next_attempt_at": row["next_attempt_at"],
            "logs": get_logs(msg_pk),
        }
    except Exception as e:
        abort(500, description=f"Failed to load status: {e}")
    return jsonify(data)


@app.route("/webhooks/bounce", methods=["POST"])
@require_webhook_secret
def webhook_bounce():
    payload = _json()
    message_id = payload.get("message_id")
    smtp_message_id = payload.get("smtp_message_id")
    email = payload.get("email")
    reason = payload.get("reason") or "bounce"
    msg_pk = mark_bounce_or_complaint("bounced", message_id=message_id, smtp_message_id=smtp_message_id, email=email, reason=reason)
    if not msg_pk:
        return jsonify({"status": "ignored", "detail": "Message not found"}), 202
    return jsonify({"status": "ok", "id": msg_pk})


@app.route("/webhooks/complaint", methods=["POST"])
@require_webhook_secret
def webhook_complaint():
    payload = _json()
    message_id = payload.get("message_id")
    smtp_message_id = payload.get("smtp_message_id")
    email = payload.get("email")
    reason = payload.get("reason") or "complaint"
    msg_pk = mark_bounce_or_complaint("complained", message_id=message_id, smtp_message_id=smtp_message_id, email=email, reason=reason)
    if not msg_pk:
        return jsonify({"status": "ignored", "detail": "Message not found"}), 202
    return jsonify({"status": "ok", "id": msg_pk})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



def create_app():
    return app
