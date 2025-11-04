import os
import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playbook_id TEXT NOT NULL,
    playbook_name TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    status TEXT NOT NULL,
    context TEXT,
    result TEXT,
    approval_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id INTEGER NOT NULL UNIQUE,
    status TEXT NOT NULL,
    token TEXT NOT NULL,
    requested_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT
);
"""


def ensure_instance_dir():
    os.makedirs('instance', exist_ok=True)


def connect(db_path: str):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str):
    conn = connect(db_path)
    with conn:
        conn.executescript(SCHEMA)
    conn.close()


def now_ts():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def create_action(db_path: str, playbook_id: str, playbook_name: str, alert_type: str, status: str, context: str | None):
    conn = connect(db_path)
    cur = conn.cursor()
    ts = now_ts()
    cur.execute(
        "INSERT INTO actions (playbook_id, playbook_name, alert_type, status, context, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (playbook_id, playbook_name, alert_type, status, context, ts, ts)
    )
    conn.commit()
    action_id = cur.lastrowid
    conn.close()
    return action_id


def update_action_status(db_path: str, action_id: int, status: str):
    conn = connect(db_path)
    ts = now_ts()
    with conn:
        conn.execute("UPDATE actions SET status=?, updated_at=? WHERE id=?", (status, ts, action_id))
    conn.close()


def update_action_result(db_path: str, action_id: int, result: str):
    conn = connect(db_path)
    ts = now_ts()
    with conn:
        conn.execute("UPDATE actions SET result=?, updated_at=? WHERE id=?", (result, ts, action_id))
    conn.close()


def get_action(db_path: str, action_id: int):
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM actions WHERE id=?", (action_id,))
    row = cur.fetchone()
    conn.close()
    return row


def list_actions(db_path: str, limit: int | None = None, count_only: bool = False):
    conn = connect(db_path)
    cur = conn.cursor()
    if count_only:
        cur.execute("SELECT COUNT(*) AS cnt FROM actions")
        row = cur.fetchone()
        conn.close()
        return row['cnt'] if row else 0
    if limit:
        cur.execute("SELECT * FROM actions ORDER BY created_at DESC LIMIT ?", (limit,))
    else:
        cur.execute("SELECT * FROM actions ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


def create_approval(db_path: str, action_id: int, token: str, expires_at: str | None):
    conn = connect(db_path)
    ts = now_ts()
    with conn:
        conn.execute(
            "INSERT INTO approvals (action_id, status, token, requested_by, created_at, updated_at, expires_at) VALUES (?, 'pending', ?, 'system', ?, ?, ?)",
            (action_id, token, ts, ts, expires_at)
        )
        approval_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
        conn.execute("UPDATE actions SET approval_id=?, updated_at=? WHERE id=?", (approval_id, ts, action_id))
    conn.close()
    return approval_id


def get_approval(db_path: str, approval_id: int):
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM approvals WHERE id=?", (approval_id,))
    row = cur.fetchone()
    conn.close()
    return row


def update_approval_status(db_path: str, approval_id: int, status: str):
    conn = connect(db_path)
    ts = now_ts()
    with conn:
        conn.execute("UPDATE approvals SET status=?, updated_at=? WHERE id=?", (status, ts, approval_id))
    conn.close()


def list_pending_approvals(db_path: str):
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM approvals WHERE status='pending' ORDER BY created_at ASC")
    rows = cur.fetchall()
    conn.close()
    return rows

