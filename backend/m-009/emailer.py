import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
from flask import render_template


def _ensure_outbox(path: str):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass


def _compose_email(app, digest_data, recipients):
    subject = f"Dependency Security Digest - {digest_data.get('app_name')} - {digest_data.get('generated_at')}"

    html_body = render_template("email_digest.html", **digest_data)
    text_body = render_template("email_digest.txt", **digest_data)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = app.config.get("MAIL_FROM")
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    return msg


def _send_via_smtp(app, msg: EmailMessage):
    host = app.config.get("SMTP_HOST")
    port = app.config.get("SMTP_PORT")
    user = app.config.get("SMTP_USERNAME")
    pwd = app.config.get("SMTP_PASSWORD")
    use_tls = app.config.get("SMTP_USE_TLS", True)
    use_ssl = app.config.get("SMTP_USE_SSL", False)

    if not host:
        raise RuntimeError("SMTP_HOST is not configured")

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port)
    else:
        server = smtplib.SMTP(host, port)

    try:
        server.ehlo()
        if use_tls and not use_ssl:
            server.starttls()
            server.ehlo()
        if user and pwd:
            server.login(user, pwd)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass


def _save_to_outbox(app, msg: EmailMessage, recipient: str):
    outbox = app.config.get("OUTBOX_DIR", "outbox")
    _ensure_outbox(outbox)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_rec = recipient.replace("@", "_at_").replace("<", "").replace(">", "").replace(" ", "_")
    path = os.path.join(outbox, f"digest_to_{safe_rec}_{ts}.eml")
    with open(path, "wb") as f:
        f.write(bytes(msg))
    return path


def _parse_owner_emails(app, override=None):
    if override:
        return [e.strip() for e in override if e.strip()]
    owners = app.config.get("OWNER_EMAILS", "")
    return [e.strip() for e in owners.split(",") if e.strip()]


def send_digest_to_owners(app, digest_data, recipients=None):
    recipients = _parse_owner_emails(app, recipients)
    if not recipients:
        return {"ok": False, "error": "No recipients configured"}

    msg = _compose_email(app, digest_data, recipients)

    try:
        _send_via_smtp(app, msg)
        app.logger.info("Digest email sent to: %s", ", ".join(recipients))
        return {"ok": True, "sent_to": recipients}
    except Exception as e:
        # Fallback: write to outbox
        app.logger.warning("SMTP send failed (%s). Writing to outbox.", e)
        paths = []
        for rcpt in recipients:
            # Duplicate message per recipient for saved files (adjust To header)
            per_msg = EmailMessage()
            for k, v in msg.items():
                if k not in ("To",):
                    per_msg[k] = v
            per_msg["To"] = rcpt
            per_msg.set_content(msg.get_body(preferencelist=('plain',)).get_content())
            html_part = msg.get_body(preferencelist=('html',))
            if html_part is not None:
                per_msg.add_alternative(html_part.get_content(), subtype="html")
            path = _save_to_outbox(app, per_msg, rcpt)
            paths.append(path)
        return {"ok": False, "saved_to_outbox": paths, "error": str(e)}

