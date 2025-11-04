import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from config import DB_PATH, MAX_RETRIES_DEFAULT, BACKOFF_BASE_SECONDS, BACKOFF_MAX_SECONDS

_DB_LOCK = threading.Lock()

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        to_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        template_name TEXT NOT NULL,
        template_vars TEXT NOT NULL,
        status TEXT NOT NULL,
        last_error TEXT,
        retries INTEGER NOT NULL DEFAULT 0,
        max_retries INTEGER NOT NULL DEFAULT 5,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        sent_at TEXT,
        message_id TEXT UNIQUE NOT NULL,
        smtp_message_id TEXT,
        provider TEXT DEFAULT 'smtp',
        next_attempt_at TEXT NOT NULL
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_messages_status_next ON messages(status, next_attempt_at);
    """,
    """
    CREATE TABLE IF NOT EXISTS message_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_pk INTEGER NOT NULL,
        event TEXT NOT NULL,
        detail TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(message_pk) REFERENCES messages(id)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_message_logs_message_pk ON message_logs(message_pk);
    """
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)  # autocommit mode
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            for stmt in SCHEMA:
                conn.execute(stmt)
        finally:
            conn.close()


def _utcnow_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def enqueue_message(to_email: str, subject: str, template_name: str, template_vars: Dict[str, Any], message_id: str, max_retries: Optional[int] = None) -> int:
    init_db()
    if max_retries is None:
        max_retries = MAX_RETRIES_DEFAULT
    now = _utcnow_str()
    payload = json.dumps(template_vars or {})
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cur = conn.execute(
                """
                INSERT INTO messages (to_email, subject, template_name, template_vars, status, last_error, retries, max_retries, created_at, updated_at, sent_at, message_id, smtp_message_id, provider, next_attempt_at)
                VALUES (?, ?, ?, ?, 'queued', NULL, 0, ?, ?, ?, NULL, ?, NULL, 'smtp', ?)
                """,
                (to_email, subject, template_name, payload, max_retries, now, now, message_id, now),
            )
            msg_pk = cur.lastrowid
            conn.execute("COMMIT;")
            _log_event(conn, msg_pk, "queued", f"Message enqueued with message_id={message_id}")
            return msg_pk
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()


def claim_next_message() -> Optional[sqlite3.Row]:
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                """
                SELECT id FROM messages
                WHERE status = 'queued' AND next_attempt_at <= ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (_utcnow_str(),),
            ).fetchone()
            if not row:
                conn.execute("COMMIT;")
                return None
            msg_pk = row[0]
            res = conn.execute(
                "UPDATE messages SET status='processing', updated_at=? WHERE id=? AND status='queued'",
                (_utcnow_str(), msg_pk),
            )
            if res.rowcount != 1:
                conn.execute("ROLLBACK;")
                return None
            conn.execute("COMMIT;")
            full = get_message(msg_pk)
            return full
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()


def set_status(msg_pk: int, status: str, error: Optional[str] = None, smtp_message_id: Optional[str] = None) -> None:
    init_db()
    now = _utcnow_str()
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            sent_at = now if status == 'sent' else None
            conn.execute(
                "UPDATE messages SET status=?, last_error=?, updated_at=?, sent_at=COALESCE(?, sent_at), smtp_message_id=COALESCE(?, smtp_message_id) WHERE id=?",
                (status, error, now, sent_at, smtp_message_id, msg_pk),
            )
            conn.execute("COMMIT;")
            _log_event(conn, msg_pk, status, error or ("Message marked as " + status))
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()


def increment_retry_and_schedule(msg_pk: int, retries: int) -> None:
    # Exponential backoff with cap
    delay = min(BACKOFF_BASE_SECONDS * (2 ** max(retries - 1, 0)), BACKOFF_MAX_SECONDS)
    next_time = datetime.utcnow() + timedelta(seconds=delay)
    next_time_str = next_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    now = _utcnow_str()
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                "UPDATE messages SET status='queued', retries=retries, next_attempt_at=?, updated_at=? WHERE id=?",
                (next_time_str, now, msg_pk),
            )
            conn.execute("COMMIT;")
            _log_event(conn, msg_pk, "retry_scheduled", f"Retry {retries} scheduled at {next_time_str}")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()


def _log_event(conn: sqlite3.Connection, msg_pk: int, event: str, detail: Optional[str]) -> None:
    conn.execute(
        "INSERT INTO message_logs (message_pk, event, detail, created_at) VALUES (?, ?, ?, ?)",
        (msg_pk, event, (detail or "")[:1000], _utcnow_str()),
    )


def log_event(msg_pk: int, event: str, detail: Optional[str]) -> None:
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            _log_event(conn, msg_pk, event, detail)
        finally:
            conn.close()


def get_message(msg_pk: int) -> Optional[sqlite3.Row]:
    init_db()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM messages WHERE id=?", (msg_pk,)).fetchone()
        return row
    finally:
        conn.close()


def get_message_by_message_id(message_id: str) -> Optional[sqlite3.Row]:
    init_db()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM messages WHERE message_id=?", (message_id,)).fetchone()
        return row
    finally:
        conn.close()


def get_message_by_smtp_message_id(smtp_message_id: str) -> Optional[sqlite3.Row]:
    init_db()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM messages WHERE smtp_message_id=?", (smtp_message_id,)).fetchone()
        return row
    finally:
        conn.close()


def get_logs(msg_pk: int):
    init_db()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, event, detail, created_at FROM message_logs WHERE message_pk=? ORDER BY id ASC",
            (msg_pk,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_bounce_or_complaint(kind: str, message_id: Optional[str] = None, smtp_message_id: Optional[str] = None, email: Optional[str] = None, reason: Optional[str] = None) -> Optional[int]:
    if kind not in ("bounced", "complained"):
        raise ValueError("Invalid kind")
    row = None
    if message_id:
        row = get_message_by_message_id(message_id)
    if not row and smtp_message_id:
        row = get_message_by_smtp_message_id(smtp_message_id)
    if not row:
        return None
    msg_pk = row["id"]
    set_status(msg_pk, "bounced" if kind == "bounced" else "complained", error=reason or kind)
    log_event(msg_pk, kind, f"{kind} via webhook for email={email or row['to_email']}; reason={reason or ''}")
    return msg_pk

