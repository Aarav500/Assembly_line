import sqlite3
import time
from typing import Any, Dict, Optional, Tuple

_conn_cache = {}


def _get_conn(db_path: str) -> sqlite3.Connection:
    # Create a new connection each time to be thread-safe; sqlite3 is light
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str):
    conn = _get_conn(db_path)
    cur = conn.cursor()

    cur.execute(
        '''CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            data TEXT
        )'''
    )

    cur.execute(
        '''CREATE TABLE IF NOT EXISTS actions (
            id TEXT PRIMARY KEY,
            incident_id TEXT,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            result TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY(incident_id) REFERENCES incidents(id)
        )'''
    )

    cur.execute(
        '''CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            timestamp INTEGER NOT NULL,
            actor TEXT,
            action TEXT NOT NULL,
            target TEXT,
            status TEXT NOT NULL,
            detail TEXT
        )'''
    )

    conn.commit()
    conn.close()


def execute(db_path: str, sql: str, params: Tuple = ()) -> int:
    conn = _get_conn(db_path)
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    lastrowid = cur.lastrowid
    conn.close()
    return lastrowid


def query_one(db_path: str, sql: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
    conn = _get_conn(db_path)
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def query_all(db_path: str, sql: str, params: Tuple = ()) -> Any:
    conn = _get_conn(db_path)
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

