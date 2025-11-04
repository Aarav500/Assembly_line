import time
import uuid
from typing import Optional

from config import Config
from models import db


def log_audit(actor: Optional[str], action: str, target: Optional[str], status: str, detail: Optional[str] = None) -> str:
    audit_id = str(uuid.uuid4())
    ts = int(time.time())
    db.execute(
        Config.DB_PATH,
        'INSERT INTO audit_logs (id, timestamp, actor, action, target, status, detail) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (audit_id, ts, actor, action, target, status, detail or ''),
    )
    return audit_id


def list_audit(limit: int = 200, offset: int = 0):
    return db.query_all(Config.DB_PATH, 'SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?', (limit, offset))

