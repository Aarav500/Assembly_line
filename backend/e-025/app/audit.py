from .db import db
from .models import AuditEvent


def log_event(team_id: str, action: str, actor: str, environment_id: str = None, details: dict | None = None):
    ev = AuditEvent(team_id=team_id, action=action, actor=actor, environment_id=environment_id)
    ev.details = details or {}
    db.session.add(ev)
    db.session.commit()
    return ev

