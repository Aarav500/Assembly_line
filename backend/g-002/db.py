import sqlite3
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import config
from retry import compute_backoff_seconds


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=30, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                name TEXT,
                created_at TEXT,
                updated_at TEXT,
                status TEXT,
                params TEXT,
                progress REAL,
                current_epoch INTEGER,
                total_epochs INTEGER,
                attempt_count INTEGER,
                max_retries INTEGER,
                next_run_at TEXT,
                last_error TEXT,
                checkpoint_path TEXT,
                log_path TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_status_next ON jobs(status, next_run_at);
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                attempt_num INTEGER,
                started_at TEXT,
                ended_at TEXT,
                status TEXT,
                error TEXT,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );
            """
        )


def create_job(params: Dict[str, Any], name: Optional[str], total_epochs: int, checkpoint_path: str, log_path: str, max_retries: int) -> str:
    job_id = str(uuid.uuid4())
    now = utc_now_iso()
    row = (
        job_id,
        name or params.get("name"),
        now,
        now,
        "pending",
        json.dumps(params),
        0.0,
        0,
        total_epochs,
        0,
        max_retries,
        now,  # next_run_at
        None,
        checkpoint_path,
        log_path,
    )
    conn = get_connection()
    with conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, name, created_at, updated_at, status, params, progress, current_epoch, total_epochs, attempt_count,
                max_retries, next_run_at, last_error, checkpoint_path, log_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            row,
        )
    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.execute("SELECT * FROM jobs WHERE id = ?;", (job_id,))
    row = cur.fetchone()
    if not row:
        return None
    return dict(row)


def list_jobs(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.execute(
        "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?;",
        (limit,),
    )
    return [dict(r) for r in cur.fetchall()]


def update_job_fields(job_id: str, fields: Dict[str, Any]) -> None:
    if not fields:
        return
    fields["updated_at"] = utc_now_iso()
    keys = list(fields.keys())
    placeholders = ", ".join([f"{k} = ?" for k in keys])
    values = [fields[k] for k in keys]
    values.append(job_id)
    conn = get_connection()
    with conn:
        conn.execute(f"UPDATE jobs SET {placeholders} WHERE id = ?;", tuple(values))


def get_attempts(job_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.execute(
        "SELECT * FROM attempts WHERE job_id = ? ORDER BY attempt_num ASC;",
        (job_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def find_jobs_ready(now_iso: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    now_iso = now_iso or utc_now_iso()
    conn = get_connection()
    cur = conn.execute(
        """
        SELECT * FROM jobs
        WHERE status IN ('pending','retrying')
          AND next_run_at <= ?
        ORDER BY created_at ASC
        LIMIT ?;
        """,
        (now_iso, limit),
    )
    return [dict(r) for r in cur.fetchall()]


def mark_queued(job_id: str) -> None:
    update_job_fields(job_id, {"status": "queued"})


def start_attempt(job_id: str) -> Tuple[int, int]:
    conn = get_connection()
    with conn:
        # Read current attempt_count and max_retries
        row = conn.execute("SELECT attempt_count FROM jobs WHERE id = ?;", (job_id,)).fetchone()
        if not row:
            raise ValueError("Job not found")
        current_attempt = int(row[0]) if row[0] is not None else 0
        attempt_num = current_attempt + 1
        conn.execute(
            "UPDATE jobs SET attempt_count = ?, status = 'running', updated_at = ? WHERE id = ?;",
            (attempt_num, utc_now_iso(), job_id),
        )
        conn.execute(
            "INSERT INTO attempts (job_id, attempt_num, started_at, status) VALUES (?, ?, ?, ?);",
            (job_id, attempt_num, utc_now_iso(), "running"),
        )
        attempt_row = conn.execute(
            "SELECT id FROM attempts WHERE job_id = ? AND attempt_num = ?;",
            (job_id, attempt_num),
        ).fetchone()
        attempt_id = int(attempt_row[0])
    return attempt_id, attempt_num


def complete_attempt(attempt_id: int, status: str, error: Optional[str] = None) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE attempts SET ended_at = ?, status = ?, error = ? WHERE id = ?;",
            (utc_now_iso(), status, error, attempt_id),
        )


def mark_job_completed(job_id: str) -> None:
    update_job_fields(job_id, {"status": "completed", "progress": 1.0})


def mark_job_canceled(job_id: str) -> None:
    update_job_fields(job_id, {"status": "canceled"})


def request_cancel(job_id: str) -> None:
    update_job_fields(job_id, {"status": "cancel_requested"})


def mark_job_retrying(job_id: str, attempt_num: int, last_error: str) -> None:
    # Compute backoff and set next_run_at accordingly; if no retries left, mark failed
    conn = get_connection()
    row = conn.execute("SELECT max_retries, attempt_count FROM jobs WHERE id = ?;", (job_id,)).fetchone()
    if not row:
        return
    max_retries = int(row[0]) if row[0] is not None else 0
    attempt_count = int(row[1]) if row[1] is not None else attempt_num

    if attempt_count >= max_retries:
        update_job_fields(job_id, {"status": "failed", "last_error": last_error})
        return

    delay = compute_backoff_seconds(attempt_count)
    next_run = datetime.now(timezone.utc) + delay
    update_job_fields(
        job_id,
        {
            "status": "retrying",
            "next_run_at": next_run.isoformat(),
            "last_error": last_error,
        },
    )


def update_progress(job_id: str, current_epoch: int, total_epochs: int) -> None:
    progress = max(0.0, min(1.0, current_epoch / float(total_epochs if total_epochs else 1)))
    update_job_fields(job_id, {"current_epoch": current_epoch, "total_epochs": total_epochs, "progress": progress})


def count_backlog() -> Dict[str, int]:
    conn = get_connection()
    queued = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'queued';").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('pending','retrying') AND next_run_at <= ?;", (utc_now_iso(),)).fetchone()[0]
    running = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'running';").fetchone()[0]
    return {"queued": int(queued), "pending": int(pending), "running": int(running)}

