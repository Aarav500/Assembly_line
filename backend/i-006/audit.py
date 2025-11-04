import os
from datetime import datetime
from flask import g, request
from models import db, AuditEvent
from config import Config


def redact(msg: str) -> str:
    if not msg:
        return msg
    # Minimal redaction to avoid accidentally logging base64 blobs or secrets
    return msg[:200]


def audit_event(action: str, object_type: str, object_id: str | None, success: bool, message: str | None = None):
    try:
        user = getattr(g, 'user', {'user_id': 'anonymous', 'role': 'unknown', 'tenant_id': None})
        evt = AuditEvent(
            actor_id=user.get('user_id'),
            actor_role=user.get('role'),
            tenant_id=user.get('tenant_id'),
            action=action,
            object_type=object_type,
            object_id=object_id,
            success=success,
            ip=(request.remote_addr if request else None),
            message=redact(message)
        )
        db.session.add(evt)
        db.session.commit()
        try:
            with open(Config.AUDIT_LOG_PATH, 'a', encoding='utf-8') as f:
                f.write(f"{evt.ts.isoformat()} {evt.actor_id} {evt.actor_role} {evt.tenant_id} {evt.ip} {evt.action} {evt.object_type} {evt.object_id} success={evt.success} msg={evt.message}\n")
        except Exception:
            pass
    except Exception:
        db.session.rollback()
        # Avoid raising in audit path
        pass

