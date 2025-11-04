import os
import json
import sqlite3
import uuid
from datetime import datetime
from contextlib import contextmanager


def now_iso():
    return datetime.utcnow().isoformat() + "Z"


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True) if os.path.dirname(db_path) else None
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _cursor(self):
        conn = self._connect()
        try:
            cur = conn.cursor()
            yield cur
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS flows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_step_index INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id TEXT PRIMARY KEY,
                    flow_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    step_name TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(flow_id) REFERENCES flows(id)
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    flow_id TEXT NOT NULL,
                    step_index INTEGER,
                    step_name TEXT,
                    status TEXT NOT NULL,
                    message TEXT,
                    details_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(flow_id) REFERENCES flows(id)
                );
                """
            )

    def create_flow(self, name: str, state: dict, status: str = "running", current_step_index: int = 0):
        flow_id = str(uuid.uuid4())
        created = now_iso()
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO flows (id, name, status, current_step_index, state_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (flow_id, name, status, current_step_index, json.dumps(state), created, created),
            )
        return flow_id

    def update_flow(self, flow_id: str, **fields):
        if not fields:
            return
        allowed = {"name", "status", "current_step_index", "state"}
        updates = []
        params = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "state":
                updates.append("state_json = ?")
                params.append(json.dumps(v))
            else:
                updates.append(f"{k} = ?")
                params.append(v)
        updates.append("updated_at = ?")
        params.append(now_iso())
        params.append(flow_id)
        with self._cursor() as cur:
            cur.execute(f"UPDATE flows SET {', '.join(updates)} WHERE id = ?", params)

    def get_flow(self, flow_id: str):
        with self._cursor() as cur:
            cur.execute("SELECT * FROM flows WHERE id = ?", (flow_id,))
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_flow(row)

    def list_flows(self, name=None, status=None, limit=100, offset=0):
        query = "SELECT * FROM flows"
        conditions = []
        params = []
        if name:
            conditions.append("name = ?")
            params.append(name)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return [self._row_to_flow(r) for r in rows]

    def add_checkpoint(self, flow_id: str, step_index: int, step_name: str, state: dict):
        ck_id = str(uuid.uuid4())
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO checkpoints (id, flow_id, step_index, step_name, state_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (ck_id, flow_id, step_index, step_name, json.dumps(state), now_iso()),
            )
        return ck_id

    def get_checkpoints(self, flow_id: str):
        with self._cursor() as cur:
            cur.execute("SELECT * FROM checkpoints WHERE flow_id = ? ORDER BY created_at ASC", (flow_id,))
            rows = cur.fetchall()
        return [self._row_to_checkpoint(r) for r in rows]

    def get_checkpoint(self, checkpoint_id: str):
        with self._cursor() as cur:
            cur.execute("SELECT * FROM checkpoints WHERE id = ?", (checkpoint_id,))
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_checkpoint(row)

    def add_execution_log(self, flow_id: str, step_index: int | None, step_name: str | None, status: str, message: str | None, details: dict | None):
        exec_id = str(uuid.uuid4())
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO executions (id, flow_id, step_index, step_name, status, message, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (exec_id, flow_id, step_index, step_name, status, message, json.dumps(details or {}), now_iso()),
            )
        return exec_id

    def get_executions(self, flow_id: str):
        with self._cursor() as cur:
            cur.execute("SELECT * FROM executions WHERE flow_id = ? ORDER BY created_at ASC", (flow_id,))
            rows = cur.fetchall()
        return [self._row_to_execution(r) for r in rows]

    def _row_to_flow(self, row: sqlite3.Row):
        return {
            "id": row["id"],
            "name": row["name"],
            "status": row["status"],
            "current_step_index": row["current_step_index"],
            "state": json.loads(row["state_json"]) if row["state_json"] else {},
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _row_to_checkpoint(self, row: sqlite3.Row):
        return {
            "id": row["id"],
            "flow_id": row["flow_id"],
            "step_index": row["step_index"],
            "step_name": row["step_name"],
            "state": json.loads(row["state_json"]) if row["state_json"] else {},
            "created_at": row["created_at"],
        }

    def _row_to_execution(self, row: sqlite3.Row):
        return {
            "id": row["id"],
            "flow_id": row["flow_id"],
            "step_index": row["step_index"],
            "step_name": row["step_name"],
            "status": row["status"],
            "message": row["message"],
            "details": json.loads(row["details_json"]) if row["details_json"] else {},
            "created_at": row["created_at"],
        }

