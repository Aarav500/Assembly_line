import base64
import json
import os
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any

from flask import current_app

from models import db, Submission

# Purpose-specific minimal field allowances
PURPOSE_RULES = {
    'feedback': {
        'allowed_fields': {'content'},
        'optional_fields': set(),
        'requires_email': False,
        'max_content_bytes': 2048,
        'description': 'Anonymous feedback collection. Email not allowed.'
    },
    'support_request': {
        'allowed_fields': {'content', 'email'},
        'optional_fields': {'email'},
        'requires_email': False,
        'max_content_bytes': 4096,
        'description': 'Support requests may include an email for follow-up.'
    },
}


def minimize_payload(payload: Dict[str, Any], purpose: str) -> Dict[str, Any]:
    rules = PURPOSE_RULES.get(purpose)
    if not rules:
        raise ValueError('Unsupported purpose')

    minimized: Dict[str, Any] = {}
    for field in rules['allowed_fields']:
        if field in payload:
            minimized[field] = payload[field]

    # Enforce size limits
    if 'content' in minimized and isinstance(minimized['content'], str):
        raw = minimized['content'].encode('utf-8')
        max_len = rules.get('max_content_bytes', 2048)
        if len(raw) > max_len:
            minimized['content'] = raw[:max_len].decode('utf-8', errors='ignore')

    # Remove empty strings
    for k in list(minimized.keys()):
        if minimized[k] == '' or minimized[k] is None:
            minimized.pop(k)

    # Disallow email if not permitted
    if 'email' in minimized and 'email' not in rules['allowed_fields']:
        minimized.pop('email', None)

    return minimized


def submission_token(submission_id: str) -> str:
    secret = os.getenv('ACCESS_TOKEN_SECRET')
    if not secret:
        raise RuntimeError('ACCESS_TOKEN_SECRET is required')
    mac = hmac.new(secret.encode('utf-8'), submission_id.encode('utf-8'), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac)[:32].decode('ascii')


def verify_submission_token(submission_id: str, token: str) -> bool:
    try:
        expected = submission_token(submission_id)
        return hmac.compare_digest(expected, token)
    except Exception:
        return False


def run_retention_once():
    now = datetime.utcnow()
    expired = Submission.query.filter(Submission.expires_at <= now).all()
    if not expired:
        return
    ids = [s.id for s in expired]
    for s in expired:
        db.session.delete(s)
    db.session.commit()

    # Minimal audit without PII
    from models import AuditEvent
    for sid in ids:
        db.session.add(AuditEvent(submission_id=None, event_type=f'purged:{sid}'))
    db.session.commit()

