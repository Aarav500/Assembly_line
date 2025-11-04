import json
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, Optional

import logging

logger = logging.getLogger("spot.queue")


class JobQueue:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA busy_timeout=5000;")
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self.lock:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT,
                    status TEXT CHECK(status IN ('queued','processing','done','failed')) NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def reset_stale_processing(self):
        # On startup, return any in-flight jobs to queue to ensure at-least-once
        now = datetime.utcnow().isoformat() + "Z"
        with self.lock:
            cur = self.conn.execute(
                "UPDATE jobs SET status='queued', updated_at=? WHERE status='processing'",
                (now,),
            )
            if cur.rowcount:
                logger.warning("Reset %d in-flight jobs to queued", cur.rowcount)

    def enqueue(self, payload: Any) -> int:
        now = datetime.utcnow().isoformat() + "Z"
        dump = json.dumps(payload, separators=(",", ":"))
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO jobs (payload, status, attempts, created_at, updated_at) VALUES (?, 'queued', 0, ?, ?)",
                (dump, now, now),
            )
            return int(cur.lastrowid)

    def fetch_and_claim_next(self) -> Optional[Dict[str, Any]]:
        now = datetime.utcnow().isoformat() + "Z"
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE;")
            row = self.conn.execute(
                "SELECT id, payload, attempts FROM jobs WHERE status='queued' ORDER BY id ASC LIMIT 1;"
            ).fetchone()
            if not row:
                self.conn.execute("COMMIT;")
                return None
            job_id, payload, attempts = row
            cur = self.conn.execute(
                "UPDATE jobs SET status='processing', attempts=attempts+1, updated_at=? WHERE id=? AND status='queued'",
                (now, job_id),
            )
            self.conn.execute("COMMIT;")
            if cur.rowcount == 0:
                return None
            return {"id": job_id, "payload": json.loads(payload), "attempts": attempts + 1}

    def mark_done(self, job_id: int):
        now = datetime.utcnow().isoformat() + "Z"
        with self.lock:
            self.conn.execute(
                "UPDATE jobs SET status='done', updated_at=?, error=NULL WHERE id=?",
                (now, job_id),
            )

    def mark_failed(self, job_id: int, error: str):
        now = datetime.utcnow().isoformat() + "Z"
        with self.lock:
            self.conn.execute(
                "UPDATE jobs SET status='failed', updated_at=?, error=? WHERE id=?",
                (now, error[:1000], job_id),
            )

    def heartbeat(self, job_id: int):
        now = datetime.utcnow().isoformat() + "Z"
        with self.lock:
            self.conn.execute(
                "UPDATE jobs SET updated_at=? WHERE id=?",
                (now, job_id),
            )

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            row = self.conn.execute(
                "SELECT id, payload, status, attempts, error, created_at, updated_at FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "payload": json.loads(row[1]) if row[1] else None,
            "status": row[2],
            "attempts": row[3],
            "error": row[4],
            "created_at": row[5],
            "updated_at": row[6],
        }

    def metrics(self) -> Dict[str, int]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT status, COUNT(*) FROM jobs GROUP BY status"
            ).fetchall()
        return {status: count for status, count in rows}

