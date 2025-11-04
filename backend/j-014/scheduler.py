import json
import threading
import time
from datetime import datetime
from typing import Optional

from db import get_connection, utcnow_iso
from tasks import TASKS, CancelledException


ALLOWED_CREATE_STATUSES = ("PENDING", "SCHEDULED")
CANCEL_REQUESTED = "CANCEL_REQUESTED"


class TaskContext:
    def __init__(self, job_id: int):
        self.job_id = job_id

    def log(self, message: str, level: str = 'INFO'):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO logs (job_id, ts, level, message) VALUES (?, ?, ?, ?)',
            (self.job_id, utcnow_iso(), level, message)
        )
        # Update last heartbeat and message
        cur.execute(
            'UPDATE jobs SET last_heartbeat = ?, message = ? WHERE id = ?',
            (utcnow_iso(), message[:500], self.job_id)
        )
        conn.commit()
        conn.close()

    def progress(self, pct: int):
        if pct < 0:
            pct = 0
        if pct > 100:
            pct = 100
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            'UPDATE jobs SET progress = ?, last_heartbeat = ? WHERE id = ?',
            (pct, utcnow_iso(), self.job_id)
        )
        conn.commit()
        conn.close()

    def ensure_not_cancelled(self):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT status FROM jobs WHERE id = ?', (self.job_id,))
        row = cur.fetchone()
        conn.close()
        if row and row['status'] == CANCEL_REQUESTED:
            raise CancelledException("Cancellation requested")


class Scheduler(threading.Thread):
    def __init__(self, poll_interval: float = 1.0):
        super().__init__(daemon=True)
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            claimed = self._claim_and_run_next_due_job()
            if not claimed:
                time.sleep(self.poll_interval)

    def stop(self):
        self._stop_event.set()

    def enqueue_job(self, name: str, job_type: str, params: dict, start_at: Optional[str] = None) -> int:
        status = 'PENDING' if not start_at else 'SCHEDULED'
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO jobs (name, type, params, status, progress, created_at, start_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, job_type, json.dumps(params), status, 0, utcnow_iso(), start_at)
        )
        job_id = cur.lastrowid
        conn.commit()
        conn.close()
        return job_id

    def request_cancel(self, job_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        # Only running or scheduled/pending can be cancelled
        cur.execute('SELECT status FROM jobs WHERE id = ?', (job_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return False
        current = row['status']
        if current in ('COMPLETED', 'FAILED', 'CANCELED'):
            conn.close()
            return False
        if current == 'RUNNING':
            cur.execute('UPDATE jobs SET status = ? WHERE id = ?', (CANCEL_REQUESTED, job_id))
        else:
            # If not started yet, mark as canceled immediately
            cur.execute('UPDATE jobs SET status = ?, finished_at = ? WHERE id = ?', ('CANCELED', utcnow_iso(), job_id))
            cur.execute('INSERT INTO logs (job_id, ts, level, message) VALUES (?, ?, ?, ?)', (job_id, utcnow_iso(), 'INFO', 'Job canceled before start'))
        conn.commit()
        conn.close()
        return True

    def retry_job(self, job_id: int) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT name, type, params FROM jobs WHERE id = ?', (job_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return 0
        name, job_type, params = row['name'], row['type'], row['params']
        cur.execute(
            'INSERT INTO jobs (name, type, params, status, progress, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (name, job_type, params, 'PENDING', 0, utcnow_iso())
        )
        new_id = cur.lastrowid
        conn.commit()
        conn.close()
        return new_id

    def _claim_and_run_next_due_job(self) -> bool:
        # Attempt to claim a job atomically
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute('BEGIN IMMEDIATE')
            now_iso = utcnow_iso()
            cur.execute(
                '''
                SELECT * FROM jobs
                WHERE status IN ('PENDING','SCHEDULED')
                  AND (start_at IS NULL OR start_at <= ?)
                ORDER BY created_at ASC
                LIMIT 1
                ''',
                (now_iso,)
            )
            job = cur.fetchone()
            if not job:
                conn.commit()
                conn.close()
                return False
            # Claim it
            cur.execute(
                'UPDATE jobs SET status = ?, started_at = ?, progress = 0 WHERE id = ?',
                ('RUNNING', utcnow_iso(), job['id'])
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            conn.close()
            return False
        conn.close()

        # Run outside the transaction
        self._run_job(job['id'])
        return True

    def _run_job(self, job_id: int):
        # Load job details
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
        job = cur.fetchone()
        conn.close()
        if not job:
            return

        job_type = job['type']
        params = {}
        try:
            params = json.loads(job['params']) if job['params'] else {}
        except Exception:
            params = {}

        ctx = TaskContext(job_id)
        func = TASKS.get(job_type)

        if not func:
            ctx.log(f"Unknown job type: {job_type}", level='ERROR')
            self._mark_failed(job_id, 'Unknown job type')
            return

        try:
            ctx.log(f"Starting job: {job['name']} [{job_type}]")
            func(ctx, **params)
            # If cancel was requested and task did not raise, finalize as canceled
            status = self._get_status(job_id)
            if status == CANCEL_REQUESTED:
                self._mark_canceled(job_id)
            else:
                self._mark_completed(job_id)
        except CancelledException:
            self._mark_canceled(job_id)
            ctx.log('Job canceled', level='WARN')
        except Exception as e:
            self._mark_failed(job_id, str(e)[:1000])
            ctx.log(f"Job failed: {e}", level='ERROR')

    def _get_status(self, job_id: int) -> str:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT status FROM jobs WHERE id = ?', (job_id,))
        row = cur.fetchone()
        conn.close()
        return row['status'] if row else ''

    def _mark_completed(self, job_id: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            'UPDATE jobs SET status = ?, progress = 100, finished_at = ?, last_heartbeat = ? WHERE id = ?',
            ('COMPLETED', utcnow_iso(), utcnow_iso(), job_id)
        )
        cur.execute('INSERT INTO logs (job_id, ts, level, message) VALUES (?, ?, ?, ?)', (job_id, utcnow_iso(), 'INFO', 'Job completed'))
        conn.commit()
        conn.close()

    def _mark_failed(self, job_id: int, error: str):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            'UPDATE jobs SET status = ?, error = ?, finished_at = ?, last_heartbeat = ? WHERE id = ?',
            ('FAILED', error, utcnow_iso(), utcnow_iso(), job_id)
        )
        conn.commit()
        conn.close()

    def _mark_canceled(self, job_id: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            'UPDATE jobs SET status = ?, finished_at = ?, last_heartbeat = ? WHERE id = ?',
            ('CANCELED', utcnow_iso(), utcnow_iso(), job_id)
        )
        conn.commit()
        conn.close()

