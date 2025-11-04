import os
import sqlite3
import threading
import json
from typing import List, Optional, Dict, Any
from config import config
from utils import iso_now

DB_PATH = os.path.join(config.DATA_DIR, "app.db")

_lock = threading.Lock()

_schema = [
    """
    CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL,
        routes TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        site_slug TEXT NOT NULL,
        paths TEXT NOT NULL,
        status TEXT NOT NULL,
        result TEXT,
        error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
]


def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# Initialize schema
with _lock:
    conn = _connect()
    try:
        cur = conn.cursor()
        for stmt in _schema:
            cur.execute(stmt)
        conn.commit()
    finally:
        conn.close()


def upsert_site(slug: str, routes: List[str]) -> Dict[str, Any]:
    with _lock:
        conn = _connect()
        try:
            now = iso_now()
            routes_json = json.dumps(routes)
            conn.execute(
                "INSERT INTO sites(slug, routes, created_at) VALUES(?,?,?) "
                "ON CONFLICT(slug) DO UPDATE SET routes=excluded.routes",
                (slug, routes_json, now),
            )
            conn.commit()
        finally:
            conn.close()
    return {"slug": slug, "routes": routes}


def get_site(slug: str) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute("SELECT slug, routes, created_at FROM sites WHERE slug=?", (slug,))
            row = cur.fetchone()
        finally:
            conn.close()
    if not row:
        return None
    return {"slug": row["slug"], "routes": json.loads(row["routes"]), "created_at": row["created_at"]}


def list_sites() -> List[Dict[str, Any]]:
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute("SELECT slug, routes, created_at FROM sites ORDER BY slug ASC")
            rows = cur.fetchall()
        finally:
            conn.close()
    return [
        {"slug": r["slug"], "routes": json.loads(r["routes"]), "created_at": r["created_at"]}
        for r in rows
    ]


def create_job(job_id: str, site_slug: str, paths: List[str], status: str) -> Dict[str, Any]:
    now = iso_now()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO jobs(id, site_slug, paths, status, created_at, updated_at) VALUES(?,?,?,?,?,?)",
                (job_id, site_slug, json.dumps(paths), status, now, now),
            )
            conn.commit()
        finally:
            conn.close()
    return get_job(job_id)


def update_job(job_id: str, status: Optional[str] = None, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> Dict[str, Any]:
    now = iso_now()
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute("SELECT id FROM jobs WHERE id=?", (job_id,))
            if not cur.fetchone():
                conn.close()
                raise ValueError("Job not found")
            if status is not None and result is not None and error is not None:
                conn.execute(
                    "UPDATE jobs SET status=?, result=?, error=?, updated_at=? WHERE id=?",
                    (status, json.dumps(result), error, now, job_id),
                )
            elif status is not None and result is not None:
                conn.execute(
                    "UPDATE jobs SET status=?, result=?, updated_at=? WHERE id=?",
                    (status, json.dumps(result), now, job_id),
                )
            elif status is not None and error is not None:
                conn.execute(
                    "UPDATE jobs SET status=?, error=?, updated_at=? WHERE id=?",
                    (status, error, now, job_id),
                )
            elif status is not None:
                conn.execute(
                    "UPDATE jobs SET status=?, updated_at=? WHERE id=?",
                    (status, now, job_id),
                )
            conn.commit()
        finally:
            conn.close()
    return get_job(job_id)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute("SELECT id, site_slug, paths, status, result, error, created_at, updated_at FROM jobs WHERE id=?", (job_id,))
            row = cur.fetchone()
        finally:
            conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "site_slug": row["site_slug"],
        "paths": json.loads(row["paths"]) if row["paths"] else [],
        "status": row["status"],
        "result": json.loads(row["result"]) if row["result"] else None,
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_jobs(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "SELECT id, site_slug, paths, status, result, error, created_at, updated_at FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "site_slug": r["site_slug"],
            "paths": json.loads(r["paths"]) if r["paths"] else [],
            "status": r["status"],
            "result": json.loads(r["result"]) if r["result"] else None,
            "error": r["error"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        })
    return out

