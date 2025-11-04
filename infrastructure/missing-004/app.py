import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from datetime import datetime
from flask import Flask, request, jsonify, abort
from sqlalchemy.exc import SQLAlchemyError

from config import settings
from database import Base, engine, db_session
from models import EmailMessage, EventLog, Unsubscribe
from tasks import send_email

app = Flask(__name__)

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})

@app.route("/emails/send", methods=["POST"]) 
def queue_email():
    data = request.get_json(force=True, silent=True) or {}
    required = ["to", "subject", "template_name"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Missing required fields: {', '.join(required)}"}), 400

    to_email = data.get("to")
    subject = data.get("subject")
    template_name = data.get("template_name")
    template_context = data.get("context", {})
    provider = data.get("provider") or settings.DEFAULT_PROVIDER
    tags = data.get("tags") or []
    metadata = data.get("metadata") or {}

    unsubscribed = db_session.query(Unsubscribe).filter(Unsubscribe.email == to_email).first()
    if unsubscribed:
        return jsonify({"error": "recipient is unsubscribed"}), 400

    message = EmailMessage(
        to_email=to_email,
        subject=subject,
        template_name=template_name,
        template_context=template_context,
        provider=provider,
        status="queued",
        tags=tags,
        metadata=metadata,
    )

    try:
        db_session.add(message)
        db_session.commit()
    except SQLAlchemyError as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 500

    # Enqueue async task
    send_email.delay(str(message.id))

    return jsonify({"id": str(message.id), "status": message.status})

@app.route("/emails/<email_id>", methods=["GET"]) 
def get_email(email_id):
    message = db_session.get(EmailMessage, email_id)
    if not message:
        return jsonify({"error": "not found"}), 404
    return jsonify(message.to_dict())

@app.route("/emails", methods=["GET"]) 
def list_emails():
    status = request.args.get("status")
    q = db_session.query(EmailMessage)
    if status:
        q = q.filter(EmailMessage.status == status)
    q = q.order_by(EmailMessage.created_at.desc()).limit(100)
    return jsonify([m.to_dict() for m in q.all()])

@app.route("/queue/metrics", methods=["GET"]) 
def queue_metrics():
    counts = {}
    for s in [
        "queued",
        "sending",
        "sent",
        "delivered",
        "deferred",
        "failed",
        "bounced",
        "opened",
        "clicked",
    ]:
        counts[s] = db_session.query(EmailMessage).filter(EmailMessage.status == s).count()
    counts["total"] = db_session.query(EmailMessage).count()
    return jsonify(counts)

@app.route("/webhooks/sendgrid", methods=["POST"]) 
def sendgrid_webhook():
    # SendGrid posts an array of event objects
    try:
        events = request.get_json(force=True)
        if not isinstance(events, list):
            return jsonify({"error": "expected list of events"}), 400
    except Exception:
        return jsonify({"error": "invalid JSON"}), 400

    for ev in events:
        try:
            handle_sendgrid_event(ev)
        except Exception as e:
            # Continue processing others
            app.logger.exception("Error handling SendGrid event: %s", e)
    db_session.commit()
    return "OK", 200

@app.route("/webhooks/ses", methods=["POST"]) 
def ses_webhook():
    # Accept direct SES event payload (simplified; in production use SNS and verify signatures)
    event = request.get_json(force=True, silent=True) or {}

    try:
        handle_ses_event(event)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        app.logger.exception("SES webhook error: %s", e)
        return jsonify({"error": str(e)}), 400
    return "OK", 200


def handle_sendgrid_event(ev: dict):
    # Correlate using custom_args.email_id or sg_message_id
    email_id = None
    # Custom args may appear as 'custom_args' dict or flattened keys
    if isinstance(ev.get("custom_args"), dict):
        email_id = ev["custom_args"].get("email_id")
    if not email_id:
        email_id = ev.get("email_id") or (ev.get("unique_args", {}) if isinstance(ev.get("unique_args"), dict) else {}).get("email_id")

    message = None
    if email_id:
        message = db_session.get(EmailMessage, email_id)
    if not message and ev.get("sg_message_id"):
        message = db_session.query(EmailMessage).filter(EmailMessage.message_id == ev.get("sg_message_id")).first()

    # Log event regardless
    log = EventLog(
        email_id=message.id if message else None,
        provider="sendgrid",
        provider_event_id=str(ev.get("sg_event_id") or ev.get("sg_message_id") or ""),
        event_type=str(ev.get("event")),
        payload=ev,
    )
    db_session.add(log)

    if not message:
        return

    event_type = ev.get("event")
    ts = datetime.utcnow()

    if event_type == "processed":
        message.status = "sending"
    elif event_type == "deferred":
        message.status = "deferred"
        message.error = ev.get("reason") or "deferred"
    elif event_type == "delivered":
        message.status = "delivered"
        message.delivered_at = ts
    elif event_type == "open":
        message.opened_at = message.opened_at or ts
        message.status = "opened"
    elif event_type == "click":
        message.clicked_at = message.clicked_at or ts
        message.status = "clicked"
    elif event_type in ("bounce", "dropped"):
        message.status = "bounced"
        message.bounce_reason = ev.get("reason") or ev.get("smtp-id") or "bounced"
        # Add to unsubscribe list
        ensure_unsubscribe(message.to_email, reason=message.bounce_reason, source="sendgrid")
    elif event_type in ("spamreport",):
        message.status = "failed"
        message.error = "spamreport"
        ensure_unsubscribe(message.to_email, reason="spamreport", source="sendgrid")
    elif event_type in ("unsubscribe",):
        ensure_unsubscribe(message.to_email, reason="user_unsubscribed", source="sendgrid")

    message.updated_at = ts
    db_session.add(message)


def handle_ses_event(event: dict):
    # Simplified handling for SES direct webhook equivalent
    notification_type = event.get("notificationType") or event.get("eventType")
    mail = event.get("mail", {})
    message_id = mail.get("messageId") or event.get("mailMessageId")

    # We attach our id via headers or tags (if configured). Try headers first
    email_id = None
    headers = mail.get("headers", [])
    for h in headers:
        if str(h.get("name")).lower() == "x-email-id":
            email_id = h.get("value")
            break
    if not email_id:
        # fallback to message_id
        msg = db_session.query(EmailMessage).filter(EmailMessage.message_id == message_id).first()
    else:
        msg = db_session.get(EmailMessage, email_id)

    log = EventLog(
        email_id=msg.id if msg else None,
        provider="ses",
        provider_event_id=str(message_id or ""),
        event_type=str(notification_type or "unknown"),
        payload=event,
    )
    db_session.add(log)

    if not msg:
        return

    ts = datetime.utcnow()

    if notification_type == "Delivery":
        msg.status = "delivered"
        msg.delivered_at = ts
    elif notification_type == "Bounce":
        bounce = event.get("bounce", {})
        msg.status = "bounced"
        msg.bounce_reason = bounce.get("bounceType") or "bounced"
        ensure_unsubscribe(msg.to_email, reason=msg.bounce_reason, source="ses")
    elif notification_type == "Complaint":
        msg.status = "failed"
        msg.error = "complaint"
        ensure_unsubscribe(msg.to_email, reason="complaint", source="ses")
    elif notification_type == "Open":
        msg.opened_at = msg.opened_at or ts
        msg.status = "opened"
    elif notification_type == "Click":
        msg.clicked_at = msg.clicked_at or ts
        msg.status = "clicked"

    msg.updated_at = ts
    db_session.add(msg)


def ensure_unsubscribe(email: str, reason: str, source: str):
    existing = db_session.query(Unsubscribe).filter(Unsubscribe.email == email).first()
    if existing:
        return existing
    unsub = Unsubscribe(email=email, reason=reason, source=source)
    db_session.add(unsub)
    return unsub

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app
