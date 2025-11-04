import os
import json
import sqlite3
from typing import Any, Dict, List, Optional


class MetricsStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._create_tables()

    def _create_tables(self):
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric TEXT NOT NULL,
                ts INTEGER NOT NULL,
                value REAL NOT NULL,
                tags TEXT
            );
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_metrics_metric_ts
            ON metrics(metric, ts);
            """
        )
        self._conn.commit()

    def insert_samples(self, rows: List[Dict[str, Any]]) -> int:
        cur = self._conn.cursor()
        cur.executemany(
            "INSERT INTO metrics(metric, ts, value, tags) VALUES (?, ?, ?, ?)",
            [
                (
                    r["metric"],
                    int(r["ts"]),
                    float(r["value"]),
                    json.dumps(r.get("tags") or {}),
                )
                for r in rows
            ],
        )
        self._conn.commit()
        return cur.rowcount

    def get_series(
        self,
        metric: str,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        limit: Optional[int] = None,
        order: str = "asc",
    ) -> List[Dict[str, Any]]:
        clauses = ["metric = ?"]
        params: List[Any] = [metric]
        if start_ts is not None:
            clauses.append("ts >= ?")
            params.append(int(start_ts))
        if end_ts is not None:
            clauses.append("ts <= ?")
            params.append(int(end_ts))
        where = " AND ".join(clauses)
        order_clause = "ASC" if order.lower() != "desc" else "DESC"
        limit_clause = f"LIMIT {int(limit)}" if limit else ""
        sql = f"SELECT ts, value, tags FROM metrics WHERE {where} ORDER BY ts {order_clause} {limit_clause}".strip()
        cur = self._conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for ts, value, tags in rows:
            try:
                tags_obj = json.loads(tags) if tags else {}
            except Exception:
                tags_obj = {}
            out.append({"ts": int(ts), "value": float(value), "tags": tags_obj})
        return out

    def get_values(
        self,
        metric: str,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        limit: Optional[int] = None,
        order: str = "asc",
    ) -> List[float]:
        series = self.get_series(metric, start_ts, end_ts, limit, order)
        return [float(p["value"]) for p in series]

