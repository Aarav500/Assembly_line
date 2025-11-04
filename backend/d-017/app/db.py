import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional


class Database:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def migrate(self):
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS runners (
                    name TEXT PRIMARY KEY,
                    container_id TEXT,
                    labels TEXT,
                    github_runner_id INTEGER,
                    status TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    last_busy_at TEXT,
                    last_online_at TEXT,
                    last_idle_since TEXT
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )
            self._conn.commit()

    def _now(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def upsert_runner(self, name: str, **fields):
        with self._lock:
            now = self._now()
            fields.setdefault("updated_at", now)
            placeholders_cols = []
            placeholders_vals = []
            params = {"name": name}
            for k, v in fields.items():
                placeholders_cols.append(k)
                placeholders_vals.append(f":{k}")
                params[k] = v
            col_list = ", ".join(["name"] + placeholders_cols + ["created_at", "updated_at"]) if "updated_at" not in fields else ", ".join(["name"] + placeholders_cols)
            val_list = ", ".join([":name"] + placeholders_vals + [":created_at", ":updated_at"]) if "updated_at" not in fields else ", ".join([":name"] + placeholders_vals)
            if "updated_at" not in fields:
                params["created_at"] = now
                params["updated_at"] = now
            sql = f"INSERT INTO runners ({col_list}) VALUES ({val_list}) ON CONFLICT(name) DO UPDATE SET " + ", ".join([f"{k}=excluded.{k}" for k in fields.keys()]) + ", updated_at=excluded.updated_at"
            self._conn.execute(sql, params)
            self._conn.commit()

    def get_runner(self, name: str) -> Optional[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM runners WHERE name=?", (name,))
            row = cur.fetchone()
            return row

    def list_runners(self) -> List[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM runners ORDER BY created_at ASC")
            return cur.fetchall()

    def list_idle_runners(self) -> List[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM runners WHERE status IN ('online','idle') ORDER BY last_idle_since ASC NULLS FIRST, created_at ASC"
            )
            return cur.fetchall()

    def delete_runner(self, name: str):
        with self._lock:
            self._conn.execute("DELETE FROM runners WHERE name=?", (name,))
            self._conn.commit()

    def set_setting(self, key: str, value: str):
        with self._lock:
            self._conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            self._conn.commit()

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._lock:
            cur = self._conn.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = cur.fetchone()
            return row[0] if row else default

    def all_settings(self) -> Dict[str, str]:
        with self._lock:
            cur = self._conn.execute("SELECT key, value FROM settings")
            return {row[0]: row[1] for row in cur.fetchall()}

    def update_runner_status_fields(self, name: str, status: str = None, github_runner_id: int = None, busy: bool = None, online: bool = None):
        fields = {}
        if status:
            fields["status"] = status
        now = self._now()
        if online is True:
            fields["last_online_at"] = now
        if busy is True:
            fields["last_busy_at"] = now
        if online and not busy:
            fields["last_idle_since"] = now
        if fields:
            self.upsert_runner(name, **fields)


