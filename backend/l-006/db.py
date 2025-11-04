import os
import sqlite3
import json
from datetime import datetime
from flask import g, current_app

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT,
    framework TEXT,
    status TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS controls (
    id INTEGER PRIMARY KEY,
    policy_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT,
    owner TEXT,
    updated_at TEXT,
    FOREIGN KEY(policy_id) REFERENCES policies(id)
);

CREATE TABLE IF NOT EXISTS evidences (
    id INTEGER PRIMARY KEY,
    control_id INTEGER,
    type TEXT,
    uri TEXT,
    collected_at TEXT,
    status TEXT,
    notes TEXT,
    FOREIGN KEY(control_id) REFERENCES controls(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY,
    actor TEXT,
    action TEXT,
    entity_type TEXT,
    entity_id INTEGER,
    timestamp TEXT,
    details_json TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    email TEXT,
    role TEXT,
    active INTEGER,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS bundles (
    id TEXT PRIMARY KEY,
    created_at TEXT,
    created_by TEXT,
    status TEXT,
    filters_json TEXT,
    file_path TEXT,
    sha256 TEXT,
    size_bytes INTEGER
);
"""


def get_db():
    if 'db' not in g:
        db_path = current_app.config['DATABASE']
        g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db_path = current_app.config['DATABASE']
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def to_dict(row):
    if not row:
        return None
    return {k: row[k] for k in row.keys()}


# Query helpers

def fetch_policies(conn, start=None, end=None, frameworks=None):
    q = "SELECT * FROM policies WHERE 1=1"
    params = []
    if start:
        q += " AND datetime(updated_at) >= datetime(?)"; params.append(start)
    if end:
        q += " AND datetime(updated_at) <= datetime(?)"; params.append(end)
    if frameworks:
        q += " AND framework IN (%s)" % (','.join(['?']*len(frameworks)))
        params.extend(frameworks)
    cur = conn.execute(q, params)
    return [to_dict(r) for r in cur.fetchall()]


def fetch_controls(conn, start=None, end=None, policy_ids=None):
    q = "SELECT * FROM controls WHERE 1=1"
    params = []
    if policy_ids:
        q += " AND policy_id IN (%s)" % (','.join(['?']*len(policy_ids)))
        params.extend(policy_ids)
    if start:
        q += " AND datetime(updated_at) >= datetime(?)"; params.append(start)
    if end:
        q += " AND datetime(updated_at) <= datetime(?)"; params.append(end)
    cur = conn.execute(q, params)
    return [to_dict(r) for r in cur.fetchall()]


def fetch_evidences(conn, start=None, end=None, control_ids=None):
    q = "SELECT * FROM evidences WHERE 1=1"
    params = []
    if control_ids:
        q += " AND control_id IN (%s)" % (','.join(['?']*len(control_ids)))
        params.extend(control_ids)
    if start:
        q += " AND datetime(collected_at) >= datetime(?)"; params.append(start)
    if end:
        q += " AND datetime(collected_at) <= datetime(?)"; params.append(end)
    cur = conn.execute(q, params)
    return [to_dict(r) for r in cur.fetchall()]


def fetch_audit_logs(conn, start=None, end=None):
    q = "SELECT * FROM audit_logs WHERE 1=1"
    params = []
    if start:
        q += " AND datetime(timestamp) >= datetime(?)"; params.append(start)
    if end:
        q += " AND datetime(timestamp) <= datetime(?)"; params.append(end)
    q += " ORDER BY datetime(timestamp) ASC"
    cur = conn.execute(q, params)
    return [to_dict(r) for r in cur.fetchall()]


def fetch_users(conn, start=None, end=None):
    q = "SELECT * FROM users WHERE 1=1"
    params = []
    if start:
        q += " AND datetime(updated_at) >= datetime(?)"; params.append(start)
    if end:
        q += " AND datetime(updated_at) <= datetime(?)"; params.append(end)
    cur = conn.execute(q, params)
    return [to_dict(r) for r in cur.fetchall()]


# Bundle persistence

def insert_bundle(conn, bundle_id, created_by, status, filters, file_path=None, sha256=None, size_bytes=None):
    conn.execute(
        "INSERT INTO bundles (id, created_at, created_by, status, filters_json, file_path, sha256, size_bytes) VALUES (?,?,?,?,?,?,?,?)",
        (bundle_id, datetime.utcnow().isoformat()+"Z", created_by, status, json.dumps(filters), file_path, sha256, size_bytes)
    )
    conn.commit()


def update_bundle(conn, bundle_id, **kwargs):
    fields = []
    params = []
    for k, v in kwargs.items():
        if k not in {"status", "file_path", "sha256", "size_bytes"}:
            continue
        fields.append(f"{k}=?")
        params.append(v)
    if not fields:
        return
    params.append(bundle_id)
    conn.execute(f"UPDATE bundles SET {', '.join(fields)} WHERE id=?", params)
    conn.commit()


def list_bundles(conn):
    cur = conn.execute("SELECT * FROM bundles ORDER BY datetime(created_at) DESC")
    return [to_dict(r) for r in cur.fetchall()]


def get_bundle(conn, bundle_id):
    cur = conn.execute("SELECT * FROM bundles WHERE id=?", (bundle_id,))
    row = cur.fetchone()
    return to_dict(row)


def delete_bundle(conn, bundle_id):
    conn.execute("DELETE FROM bundles WHERE id=?", (bundle_id,))
    conn.commit()

