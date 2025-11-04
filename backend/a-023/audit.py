import json
import hashlib
from datetime import datetime
from typing import Optional, Dict
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import AuditEvent
from utils import dt_to_iso

ZERO_HASH = '0' * 64


def compute_event_hash(prev_hash: str, project_id: int, action_type: str, user_id: str, ip: str, user_agent: str, metadata_json: str, created_at: datetime) -> str:
    parts = [
        prev_hash or ZERO_HASH,
        str(project_id),
        action_type or '',
        user_id or '',
        ip or '',
        user_agent or '',
        metadata_json or '{}',
        dt_to_iso(created_at),
    ]
    data = '|'.join(parts)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def get_last_event_hash_for_project(session: Session, project_id: int) -> str:
    stmt = select(AuditEvent.event_hash).where(AuditEvent.project_id == project_id).order_by(AuditEvent.id.desc()).limit(1)
    row = session.execute(stmt).first()
    if row:
        return row[0]
    return ZERO_HASH


def record_event(session: Session, project_id: int, action_type: str, metadata: Optional[Dict] = None, user_id: Optional[str] = None, ip: Optional[str] = None, user_agent: Optional[str] = None, created_at: Optional[datetime] = None) -> AuditEvent:
    created = created_at or datetime.utcnow()
    metadata_json = json.dumps(metadata or {}, sort_keys=True, separators=(',', ':'))
    prev_hash = get_last_event_hash_for_project(session, project_id)
    event_hash = compute_event_hash(prev_hash, project_id, action_type, user_id or '', ip or '', user_agent or '', metadata_json, created)

    ev = AuditEvent(
        project_id=project_id,
        action_type=action_type,
        user_id=user_id,
        ip=ip,
        user_agent=user_agent,
        metadata=metadata_json,
        created_at=created,
        prev_hash=prev_hash,
        event_hash=event_hash,
    )
    session.add(ev)
    session.flush()  # assign ID
    return ev


def verify_project_chain(session: Session, project_id: int):
    stmt = select(AuditEvent).where(AuditEvent.project_id == project_id).order_by(AuditEvent.id.asc())
    rows = session.execute(stmt).scalars().all()
    issues = []
    prev_hash = ZERO_HASH
    for ev in rows:
        expected = compute_event_hash(prev_hash, ev.project_id, ev.action_type, ev.user_id or '', ev.ip or '', ev.user_agent or '', ev.metadata or '{}', ev.created_at)
        if ev.prev_hash != prev_hash:
            issues.append({'id': ev.id, 'error': 'prev_hash_mismatch', 'expected_prev_hash': prev_hash, 'actual_prev_hash': ev.prev_hash})
        if ev.event_hash != expected:
            issues.append({'id': ev.id, 'error': 'event_hash_mismatch', 'expected_event_hash': expected, 'actual_event_hash': ev.event_hash})
        prev_hash = ev.event_hash
    return {'valid': len(issues) == 0, 'issues': issues, 'count': len(rows)}

