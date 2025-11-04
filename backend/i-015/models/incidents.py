import json
import time
import uuid
from typing import Any, Dict, List, Optional

from config import Config
from models import db


def _now() -> int:
    return int(time.time())


def create_incident(title: str, severity: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    incident_id = str(uuid.uuid4())
    ts = _now()
    db.execute(
        Config.DB_PATH,
        'INSERT INTO incidents (id, title, severity, status, created_at, updated_at, data) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (incident_id, title, severity, 'open', ts, ts, json.dumps(data or {})),
    )
    return get_incident(incident_id)


def get_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    return db.query_one(Config.DB_PATH, 'SELECT * FROM incidents WHERE id = ?', (incident_id,))


def list_incidents(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    return db.query_all(Config.DB_PATH, 'SELECT * FROM incidents ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset))


def update_incident_status(incident_id: str, status: str) -> None:
    ts = _now()
    db.execute(Config.DB_PATH, 'UPDATE incidents SET status = ?, updated_at = ? WHERE id = ?', (status, ts, incident_id))


def add_action(incident_id: Optional[str], action_type: str, status: str, result: Optional[Dict[str, Any]] = None) -> str:
    action_id = str(uuid.uuid4())
    ts = _now()
    db.execute(
        Config.DB_PATH,
        'INSERT INTO actions (id, incident_id, type, status, result, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (action_id, incident_id, action_type, status, json.dumps(result or {}), ts, ts),
    )
    return action_id


def update_action(action_id: str, status: str, result: Optional[Dict[str, Any]] = None) -> None:
    ts = _now()
    db.execute(
        Config.DB_PATH,
        'UPDATE actions SET status = ?, result = ?, updated_at = ? WHERE id = ?',
        (status, json.dumps(result or {}), ts, action_id),
    )


def get_action(action_id: str) -> Optional[Dict[str, Any]]:
    return db.query_one(Config.DB_PATH, 'SELECT * FROM actions WHERE id = ?', (action_id,))


def list_actions(incident_id: Optional[str] = None) -> List[Dict[str, Any]]:
    if incident_id:
        return db.query_all(Config.DB_PATH, 'SELECT * FROM actions WHERE incident_id = ? ORDER BY created_at DESC', (incident_id,))
    return db.query_all(Config.DB_PATH, 'SELECT * FROM actions ORDER BY created_at DESC', ())

