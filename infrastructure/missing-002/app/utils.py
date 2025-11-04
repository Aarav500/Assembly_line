import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable
from flask import current_app, request, jsonify, url_for
from flask_login import current_user
from flask_mail import Message
from werkzeug.security import check_password_hash, generate_password_hash
from .extensions import mail


def now_utc():
    return datetime.utcnow()


def generate_token_pair():
    # returns (plain_token, token_hash)
    token_plain = secrets.token_urlsafe(32)
    token_hash = generate_password_hash(token_plain)
    return token_plain, token_hash


def verify_token_hash(token_plain: str, token_hash: str) -> bool:
    return check_password_hash(token_hash, token_plain)


def roles_required(*role_names: str):
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "Authentication required"}), 401
            if not any(current_user.has_role(r) for r in role_names):
                return jsonify({"error": "Insufficient permissions"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def send_email(subject: str, recipients: list[str], html_body: str | None = None, text_body: str | None = None):
    if not recipients:
        return
    msg = Message(subject=subject, recipients=recipients)
    if html_body:
        msg.html = html_body
    if text_body:
        msg.body = text_body

    if current_app.config.get('MAIL_SUPPRESS_SEND', False):
        print("[Email suppressed] To:", recipients)
        print("Subject:", subject)
        print("Body:", text_body or html_body)
        return

    mail.send(msg)


def build_external_url(path: str) -> str:
    # Prefer FRONTEND_URL if provided, else build from request.url_root
    frontend = current_app.config.get('FRONTEND_URL')
    if frontend:
        return frontend.rstrip('/') + path
    base = request.url_root.rstrip('/')
    return base + path


def json_required(fields: list[str] = None):
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return jsonify({"error": "Expected application/json"}), 400
            data = request.get_json(silent=True) or {}
            if fields:
                missing = [f for f in fields if f not in data]
                if missing:
                    return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def paginate_query(query, page: int, per_page: int):
    page = max(1, int(page or 1))
    per_page = max(1, min(int(per_page or 20), 100))
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    total = query.order_by(None).count()
    return items, total, page, per_page

