from typing import Any, Optional
from uuid import uuid4
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone

from .db import get_conn, adapt_json
from .hlc import HLC
from .config import config

hlc = HLC(node_id=config.NODE_ID)


def init_db() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS kv_items (
                    key TEXT PRIMARY KEY,
                    value JSONB,
                    hlc_ts TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_kv_items_hlc ON kv_items(hlc_ts);

                CREATE TABLE IF NOT EXISTS changes (
                    seq BIGSERIAL PRIMARY KEY,
                    change_id UUID NOT NULL UNIQUE,
                    key TEXT NOT NULL,
                    value JSONB,
                    hlc_ts TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    op TEXT NOT NULL CHECK (op IN ('upsert','delete')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_changes_origin_seq ON changes(origin, seq);
                CREATE INDEX IF NOT EXISTS idx_changes_key ON changes(key);

                CREATE TABLE IF NOT EXISTS peers_sync_state (
                    peer_url TEXT PRIMARY KEY,
                    last_seq BIGINT NOT NULL DEFAULT 0,
                    last_pulled_at TIMESTAMPTZ
                );
                """
            )
            conn.commit()


def _should_apply(existing: Optional[dict], incoming_hlc: str, incoming_updated_by: str) -> bool:
    if existing is None:
        return True
    cmp = HLC.compare(incoming_hlc, existing["hlc_ts"])  # type: ignore
    if cmp > 0:
        return True
    if cmp < 0:
        return False
    # equal timestamp: tie-break by updated_by lexicographically
    return incoming_updated_by > existing["updated_by"]  # type: ignore


def create_local_change_upsert(key: str, value: Any) -> dict:
    ts = hlc.send()
    change_id = str(uuid4())
    change = {
        "change_id": change_id,
        "key": key,
        "value": value,
        "hlc_ts": ts,
        "updated_by": config.REGION_ID,
        "origin": config.REGION_ID,
        "op": "upsert",
    }
    _apply_and_record_change(change)
    return change


def create_local_change_delete(key: str) -> dict:
    ts = hlc.send()
    change_id = str(uuid4())
    change = {
        "change_id": change_id,
        "key": key,
        "value": None,
        "hlc_ts": ts,
        "updated_by": config.REGION_ID,
        "origin": config.REGION_ID,
        "op": "delete",
    }
    _apply_and_record_change(change)
    return change


def _apply_and_record_change(change: dict) -> None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Record change idempotently
            cur.execute(
                """
                INSERT INTO changes(change_id, key, value, hlc_ts, updated_by, origin, op)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (change_id) DO NOTHING
                RETURNING seq
                """,
                (
                    change["change_id"],
                    change["key"],
                    adapt_json(change["value"]),
                    change["hlc_ts"],
                    change["updated_by"],
                    change["origin"],
                    change["op"],
                ),
            )
            inserted = cur.fetchone()
            # Apply to kv if not applied or even if duplicate? We guard by change_id semantics.
            if inserted is not None:
                _apply_to_kv_locked(cur, change)
            conn.commit()


def _apply_to_kv_locked(cur, change: dict) -> None:
    # Fetch current row for key
    cur.execute("SELECT key, value, hlc_ts, updated_by, deleted FROM kv_items WHERE key = %s FOR UPDATE", (change["key"],))
    row = cur.fetchone()
    if row is None or _should_apply(row, change["hlc_ts"], change["updated_by"]):
        if change["op"] == "delete":
            cur.execute(
                """
                INSERT INTO kv_items(key, value, hlc_ts, updated_by, deleted, updated_at)
                VALUES (%s, %s, %s, %s, TRUE, NOW())
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    hlc_ts = EXCLUDED.hlc_ts,
                    updated_by = EXCLUDED.updated_by,
                    deleted = TRUE,
                    updated_at = NOW()
                """,
                (change["key"], None, change["hlc_ts"], change["updated_by"]),
            )
        else:
            cur.execute(
                """
                INSERT INTO kv_items(key, value, hlc_ts, updated_by, deleted, updated_at)
                VALUES (%s, %s, %s, %s, FALSE, NOW())
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    hlc_ts = EXCLUDED.hlc_ts,
                    updated_by = EXCLUDED.updated_by,
                    deleted = FALSE,
                    updated_at = NOW()
                """,
                (change["key"], adapt_json(change["value"]), change["hlc_ts"], change["updated_by"]),
            )


def ingest_remote_change(change: dict) -> bool:
    # Ensure local HLC moves forward after receiving
    try:
        hlc.receive(change["hlc_ts"])
    except Exception:
        pass
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # idempotent insert of change
            cur.execute(
                """
                INSERT INTO changes(change_id, key, value, hlc_ts, updated_by, origin, op)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (change_id) DO NOTHING
                RETURNING seq
                """,
                (
                    change["change_id"],
                    change["key"],
                    adapt_json(change.get("value")),
                    change["hlc_ts"],
                    change["updated_by"],
                    change.get("origin") or change["updated_by"],
                    change["op"],
                ),
            )
            inserted = cur.fetchone()
            if inserted is not None:
                _apply_to_kv_locked(cur, change)
            conn.commit()
            return inserted is not None


def get_item(key: str) -> Optional[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT key, value, hlc_ts, updated_by, deleted, updated_at FROM kv_items WHERE key = %s", (key,))
            row = cur.fetchone()
            return dict(row) if row else None


def list_changes(since_seq: int = 0, limit: int = 500, origin_only: bool = True) -> dict:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if origin_only:
                cur.execute(
                    """
                    SELECT seq, change_id, key, value, hlc_ts, updated_by, origin, op, created_at
                    FROM changes
                    WHERE seq > %s AND origin = %s
                    ORDER BY seq ASC
                    LIMIT %s
                    """,
                    (since_seq, config.REGION_ID, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT seq, change_id, key, value, hlc_ts, updated_by, origin, op, created_at
                    FROM changes
                    WHERE seq > %s
                    ORDER BY seq ASC
                    LIMIT %s
                    """,
                    (since_seq, limit),
                )
            rows = cur.fetchall()
            last_seq = rows[-1]["seq"] if rows else since_seq
            return {
                "changes": [dict(r) for r in rows],
                "last_seq": last_seq,
            }


def ensure_peer_state(peer_url: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO peers_sync_state(peer_url, last_seq, last_pulled_at)
                VALUES (%s, 0, NOW())
                ON CONFLICT (peer_url) DO NOTHING
                """,
                (peer_url,),
            )
            conn.commit()


def get_peer_last_seq(peer_url: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT last_seq FROM peers_sync_state WHERE peer_url = %s", (peer_url,))
            row = cur.fetchone()
            return int(row[0]) if row else 0


def update_peer_last_seq(peer_url: str, last_seq: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE peers_sync_state SET last_seq = %s, last_pulled_at = NOW() WHERE peer_url = %s",
                (last_seq, peer_url),
            )
            conn.commit()

