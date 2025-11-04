import json
import smtplib
from email.message import EmailMessage
from typing import List
import requests
from flask import current_app


def send_email(subject: str, body: str, to_addresses: List[str]):
    if not to_addresses:
        return

    host = current_app.config.get('SMTP_HOST', '')
    username = current_app.config.get('SMTP_USERNAME', '')
    password = current_app.config.get('SMTP_PASSWORD', '')
    port = current_app.config.get('SMTP_PORT', 587)
    use_tls = current_app.config.get('SMTP_USE_TLS', True)
    mail_from = current_app.config.get('MAIL_FROM', 'kb-diff@localhost')

    if not host:
        current_app.logger.info('SMTP not configured; skipping email notification')
        return

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = mail_from
    msg['To'] = ', '.join(to_addresses)
    msg.set_content(body)

    with smtplib.SMTP(host, port) as server:
        if use_tls:
            server.starttls()
        if username:
            server.login(username, password)
        server.send_message(msg)


def send_webhook(webhook_url: str, text: str):
    if not webhook_url:
        return
    try:
        headers = {'Content-Type': 'application/json'}
        payload = {'text': text}
        requests.post(webhook_url, headers=headers, data=json.dumps(payload), timeout=10)
    except Exception as e:
        current_app.logger.error(f'Webhook notification failed: {e}')


def notify_change(source, version, diff_url: str):
    subject = f"[KB-Diff] Changes detected: {source.name}"
    body = (
        f"Source: {source.name}\n"
        f"URL: {source.url}\n"
        f"Added lines: {version.added_lines}, Removed lines: {version.removed_lines}\n"
        f"View diff: {diff_url}\n"
    )

    # Email
    emails = []
    if source.notify_email:
        emails.extend([e.strip() for e in source.notify_email.split(',') if e.strip()])
    default_email = current_app.config.get('DEFAULT_NOTIFY_EMAIL', '')
    if default_email:
        emails.append(default_email)
    send_email(subject, body, emails)

    # Webhook
    webhook = source.notify_webhook or current_app.config.get('DEFAULT_NOTIFY_WEBHOOK', '')
    if webhook:
        send_webhook(webhook, subject + "\n" + body)

