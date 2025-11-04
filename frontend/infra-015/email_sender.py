import os
import re
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from email.utils import make_msgid, formataddr
from typing import Dict, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound

from config import SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_USE_TLS, FROM_EMAIL, FROM_NAME, APP_DOMAIN_FOR_MESSAGE_ID

_TEMPLATE_ENV = None


def _templates_path() -> str:
    return os.path.join(os.path.dirname(__file__), "templates")


def _env() -> Environment:
    global _TEMPLATE_ENV
    if _TEMPLATE_ENV is None:
        _TEMPLATE_ENV = Environment(
            loader=FileSystemLoader(_templates_path()),
            autoescape=select_autoescape(["html", "xml"]),
        )
    return _TEMPLATE_ENV


def render_templates(template_name: str, context: Dict) -> Tuple[str, str]:
    # Returns (text_body, html_body)
    env = _env()
    text_body = ""
    html_body = ""
    # Text template is optional but recommended
    try:
        ttxt = env.get_template(f"email/{template_name}.txt")
        text_body = ttxt.render(**(context or {}))
    except TemplateNotFound:
        text_body = ""
    # HTML template is optional
    try:
        thtml = env.get_template(f"email/{template_name}.html")
        html_body = thtml.render(**(context or {}))
    except TemplateNotFound:
        html_body = ""
    if not (text_body or html_body):
        raise TemplateNotFound(f"email/{template_name}(.txt|.html)")
    return text_body, html_body


_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def validate_email(addr: str) -> bool:
    return bool(addr and _EMAIL_RE.match(addr))


def send_smtp(to_email: str, subject: str, text_body: str, html_body: str, app_message_id: str) -> str:
    if not validate_email(to_email):
        raise ValueError("Invalid recipient email address")

    msg = EmailMessage()
    from_header = formataddr((FROM_NAME, FROM_EMAIL)) if FROM_NAME else FROM_EMAIL
    msg["From"] = from_header
    msg["To"] = to_email
    msg["Subject"] = subject

    # Unique IDs
    smtp_message_id = make_msgid(domain=APP_DOMAIN_FOR_MESSAGE_ID)
    msg["Message-ID"] = smtp_message_id
    msg["X-App-Message-Id"] = app_message_id

    if html_body and text_body:
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")
    elif html_body:
        msg.add_alternative(html_body, subtype="html")
    else:
        msg.set_content(text_body)

    if SMTP_USE_TLS:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=context)
            if SMTP_USERNAME:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            refused = server.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_USERNAME:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            refused = server.send_message(msg)

    if refused:
        # refused is a dict of recipients that were refused
        raise RuntimeError(f"SMTP refused recipients: {refused}")

    return smtp_message_id

