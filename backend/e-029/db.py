import json
import sqlite3
from datetime import datetime


def _connect(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def init_db(db_path):
    con = _connect(db_path)
    cur = con.cursor()
    cur.execute(
        '''CREATE TABLE IF NOT EXISTS policy (
               id INTEGER PRIMARY KEY CHECK (id = 1),
               data TEXT NOT NULL,
               updated_at TEXT NOT NULL
           )'''
    )
    cur.execute(
        '''CREATE TABLE IF NOT EXISTS enforcement_events (
               id TEXT PRIMARY KEY,
               created_at TEXT NOT NULL,
               summary TEXT,
               details TEXT,
               zip_path TEXT
           )'''
    )
    con.commit()
    con.close()


def get_policy(db_path):
    con = _connect(db_path)
    cur = con.cursor()
    cur.execute('SELECT data FROM policy WHERE id = 1')
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    return json.loads(row['data'])


def save_policy(db_path, policy_dict):
    con = _connect(db_path)
    cur = con.cursor()
    now = datetime.utcnow().isoformat() + 'Z'
    data = json.dumps(policy_dict, sort_keys=True)
    cur.execute('INSERT INTO policy (id, data, updated_at) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at', (data, now))
    con.commit()
    con.close()


def add_event(db_path, event_record):
    con = _connect(db_path)
    cur = con.cursor()
    details = event_record.get('details')
    if isinstance(details, (dict, list)):
        details = json.dumps(details, sort_keys=True)
    cur.execute(
        'INSERT INTO enforcement_events (id, created_at, summary, details, zip_path) VALUES (?, ?, ?, ?, ?)',
        (
            event_record['id'],
            event_record['created_at'],
            event_record.get('summary'),
            details,
            event_record.get('zip_path')
        )
    )
    con.commit()
    con.close()


def list_events(db_path, limit=50):
    con = _connect(db_path)
    cur = con.cursor()
    cur.execute('SELECT id, created_at, summary, zip_path FROM enforcement_events ORDER BY created_at DESC LIMIT ?', (limit,))
    rows = cur.fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_event(db_path, event_id):
    con = _connect(db_path)
    cur = con.cursor()
    cur.execute('SELECT id, created_at, summary, details, zip_path FROM enforcement_events WHERE id = ?', (event_id,))
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    data = dict(row)
    try:
        data['details'] = json.loads(data['details']) if data.get('details') else None
    except Exception:
        pass
    return data

