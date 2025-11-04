import os
import sqlite3
import hashlib
import json
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = os.environ.get('AUDIT_DB_PATH', os.path.join(os.getcwd(), 'audit.db'))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def canonical_json(obj) -> str:
    return json.dumps(obj if obj is not None else {}, sort_keys=True, separators=(',', ':'))


def summarize_text(text: str, max_chars: int = 240) -> str:
    if text is None:
        return ''
    t = str(text).strip().replace('\r\n', '\n').replace('\r', '\n')
    if len(t) <= max_chars:
        return t
    head = max_chars // 2
    tail = max_chars - head - 1
    return f"{t[:head]}\u2026{t[-tail:]}"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


@contextmanager
def tx(conn: sqlite3.Connection):
    try:
        conn.execute('BEGIN;')
        yield
        conn.execute('COMMIT;')
    except Exception:
        conn.execute('ROLLBACK;')
        raise


def init_db():
    conn = get_connection()
    with open(os.path.join(os.path.dirname(__file__), 'schema.sql'), 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.close()


def row_to_dict(row: sqlite3.Row):
    return {k: row[k] for k in row.keys()}


def get_job(conn: sqlite3.Connection, job_id: int):
    cur = conn.execute('SELECT * FROM jobs WHERE id = ?;', (job_id,))
    return cur.fetchone()


def list_entries(conn: sqlite3.Connection, job_id: int):
    cur = conn.execute('SELECT * FROM entries WHERE job_id = ? ORDER BY id ASC;', (job_id,))
    return cur.fetchall()


def get_last_entry_hash(conn: sqlite3.Connection, job_id: int):
    cur = conn.execute('SELECT entry_hash FROM entries WHERE job_id = ? AND entry_hash IS NOT NULL ORDER BY id DESC LIMIT 1;', (job_id,))
    row = cur.fetchone()
    return row['entry_hash'] if row else None


def compute_entry_hash(payload: dict) -> str:
    # Deterministic canonical serialization
    serial = canonical_json(payload)
    return sha256_hex(serial)


def create_job(name: str | None = None) -> dict:
    conn = get_connection()
    try:
        with tx(conn):
            created_at = utc_now_iso()
            cur = conn.execute('INSERT INTO jobs (name, created_at) VALUES (?, ?);', (name, created_at))
            job_id = cur.lastrowid
            job = conn.execute('SELECT * FROM jobs WHERE id = ?;', (job_id,)).fetchone()
            return row_to_dict(job)
    finally:
        conn.close()


def seal_job(job_id: int) -> dict:
    conn = get_connection()
    try:
        with tx(conn):
            job = get_job(conn, job_id)
            if job is None:
                raise ValueError('job not found')
            if job['sealed_at'] is not None:
                raise ValueError('job already sealed')
            last_hash = get_last_entry_hash(conn, job_id)
            if last_hash is None:
                # Allow sealing empty job; use SHA of empty string + job id for determinism
                last_hash = sha256_hex(f"empty:{job_id}")
            sealed_at = utc_now_iso()
            conn.execute('UPDATE jobs SET sealed_at = ?, root_hash = ? WHERE id = ?;', (sealed_at, last_hash, job_id))
            job = get_job(conn, job_id)
            return row_to_dict(job)
    finally:
        conn.close()


def append_entry(job_id: int, prompt: str, response: str, metadata: dict | None = None) -> dict:
    conn = get_connection()
    try:
        with tx(conn):
            job = get_job(conn, job_id)
            if job is None:
                raise ValueError('job not found')
            if job['sealed_at'] is not None:
                raise ValueError('job is sealed; cannot append')

            created_at = utc_now_iso()
            prev_hash = get_last_entry_hash(conn, job_id)

            prompt_summary = summarize_text(prompt)
            response_summary = summarize_text(response)
            prompt_sha = sha256_hex(prompt or '')
            response_sha = sha256_hex(response or '')
            meta_canon = canonical_json(metadata)

            cur = conn.execute(
                'INSERT INTO entries (job_id, created_at, prompt_sha256, response_sha256, prompt_summary, response_summary, metadata, prev_entry_hash)\n                 VALUES (?, ?, ?, ?, ?, ?, ?, ?);',
                (job_id, created_at, prompt_sha, response_sha, prompt_summary, response_summary, meta_canon, prev_hash)
            )
            entry_id = cur.lastrowid

            # Compute entry hash deterministically using the stored values
            payload = {
                'job_id': job_id,
                'entry_id': entry_id,
                'created_at': created_at,
                'prompt_sha256': prompt_sha,
                'response_sha256': response_sha,
                'prompt_summary': prompt_summary,
                'response_summary': response_summary,
                'metadata': json.loads(meta_canon),
                'prev_entry_hash': prev_hash,
            }
            entry_hash = compute_entry_hash(payload)

            conn.execute('UPDATE entries SET entry_hash = ? WHERE id = ?;', (entry_hash, entry_id))
            entry = conn.execute('SELECT * FROM entries WHERE id = ?;', (entry_id,)).fetchone()
            return row_to_dict(entry)
    finally:
        conn.close()


def verify_job(job_id: int) -> dict:
    conn = get_connection()
    try:
        job = get_job(conn, job_id)
        if job is None:
            raise ValueError('job not found')
        entries = list_entries(conn, job_id)
        ok = True
        issues = []
        prev_hash = None
        last_hash = None
        for row in entries:
            payload = {
                'job_id': row['job_id'],
                'entry_id': row['id'],
                'created_at': row['created_at'],
                'prompt_sha256': row['prompt_sha256'],
                'response_sha256': row['response_sha256'],
                'prompt_summary': row['prompt_summary'],
                'response_summary': row['response_summary'],
                'metadata': json.loads(row['metadata'] or '{}'),
                'prev_entry_hash': prev_hash,
            }
            expected_hash = compute_entry_hash(payload)
            if row['prev_entry_hash'] != prev_hash:
                ok = False
                issues.append({'entry_id': row['id'], 'issue': 'prev_entry_hash mismatch', 'expected_prev': prev_hash, 'found_prev': row['prev_entry_hash']})
            if row['entry_hash'] != expected_hash:
                ok = False
                issues.append({'entry_id': row['id'], 'issue': 'entry_hash mismatch', 'expected': expected_hash, 'found': row['entry_hash']})
            prev_hash = row['entry_hash']
            last_hash = row['entry_hash']
        sealed_consistent = True
        if job['sealed_at'] is not None:
            expected_root = last_hash if last_hash is not None else sha256_hex(f"empty:{job_id}")
            if job['root_hash'] != expected_root:
                ok = False
                sealed_consistent = False
                issues.append({'issue': 'root_hash mismatch', 'expected': expected_root, 'found': job['root_hash']})
        return {
            'job_id': job_id,
            'verified': ok,
            'sealed': job['sealed_at'] is not None,
            'sealed_consistent': sealed_consistent,
            'issues': issues,
            'entry_count': len(entries),
            'last_hash': last_hash,
            'root_hash': job['root_hash'],
        }
    finally:
        conn.close()

