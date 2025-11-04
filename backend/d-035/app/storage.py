import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from .config import settings

_DB_PATH = settings.db_path


def ensure_data_dir() -> None:
    d = os.path.dirname(_DB_PATH)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


@contextmanager
def get_conn() -> Iterable[sqlite3.Connection]:
    ensure_data_dir()
    conn = sqlite3.connect(_DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image TEXT NOT NULL,
                scanned_at TEXT NOT NULL,
                scanner TEXT NOT NULL,
                report_json TEXT NOT NULL,
                critical_count INTEGER NOT NULL,
                high_count INTEGER NOT NULL,
                medium_count INTEGER NOT NULL,
                low_count INTEGER NOT NULL,
                unknown_count INTEGER NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scans_image ON scans(image)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scans_scanned_at ON scans(scanned_at)")


def save_scan(
    image: str,
    scanned_at: datetime,
    scanner: str,
    report: Dict[str, Any],
    counts: Dict[str, int],
) -> int:
    doc = json.dumps(report, separators=(",", ":"))
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO scans (image, scanned_at, scanner, report_json, critical_count, high_count, medium_count, low_count, unknown_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                image,
                scanned_at.isoformat(),
                scanner,
                doc,
                int(counts.get("CRITICAL", 0)),
                int(counts.get("HIGH", 0)),
                int(counts.get("MEDIUM", 0)),
                int(counts.get("LOW", 0)),
                int(counts.get("UNKNOWN", 0)),
            ),
        )
        return int(cur.lastrowid)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "image": row["image"],
        "scanned_at": row["scanned_at"],
        "scanner": row["scanner"],
        "report": json.loads(row["report_json"] or "{}"),
        "counts": {
            "CRITICAL": row["critical_count"],
            "HIGH": row["high_count"],
            "MEDIUM": row["medium_count"],
            "LOW": row["low_count"],
            "UNKNOWN": row["unknown_count"],
        },
    }


def get_recent_scans(limit: int = 100) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM scans ORDER BY datetime(scanned_at) DESC LIMIT ?",
            (int(limit),),
        )
        return [_row_to_dict(r) for r in cur.fetchall()]


def get_scans_for_image(image: str, limit: int = 50) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM scans
            WHERE image = ?
            ORDER BY datetime(scanned_at) DESC
            LIMIT ?
            """,
            (image, int(limit)),
        )
        return [_row_to_dict(r) for r in cur.fetchall()]


def get_latest_scans_by_image() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.cursor()
        # For each image, select the latest scan
        cur.execute(
            """
            SELECT s.* FROM scans s
            JOIN (
                SELECT image, MAX(datetime(scanned_at)) as max_ts
                FROM scans
                GROUP BY image
            ) latest ON latest.image = s.image AND datetime(s.scanned_at) = latest.max_ts
            ORDER BY s.image ASC
            """
        )
        return [_row_to_dict(r) for r in cur.fetchall()]


def prune_old_scans_per_image(retain: int) -> int:
    if retain <= 0:
        return 0
    deleted_total = 0
    with get_conn() as conn:
        cur = conn.cursor()
        # Find ids to delete, keeping newest N per image
        cur.execute("SELECT DISTINCT image FROM scans")
        images = [row[0] for row in cur.fetchall()]
        for image in images:
            cur.execute(
                """
                SELECT id FROM scans WHERE image = ?
                ORDER BY datetime(scanned_at) DESC
                OFFSET ?
                """,
                (image, retain),
            )
            ids = [r[0] for r in cur.fetchall()]
            if ids:
                q = f"DELETE FROM scans WHERE id IN ({','.join('?' for _ in ids)})"
                cur.execute(q, ids)
                deleted_total += cur.rowcount
    return deleted_total

