from __future__ import annotations
from typing import Optional, Sequence
from alembic import op
import sqlalchemy as sa


def backfill_in_batches(
    table_name: str,
    set_sql: str,
    where_sql: str,
    order_by: str,
    batch_size: int = 1000,
    max_batches: Optional[int] = None,
) -> int:
    """
    Perform batched updates to avoid long-lived locks.

    Example:
    backfill_in_batches(
        table_name="users",
        set_sql="email = username || '@example.com'",
        where_sql="email IS NULL",
        order_by="id",
        batch_size=1000,
    )
    """
    conn = op.get_bind()
    total = 0
    batches = 0
    while True:
        # Use ctid to limit updates without requiring an index on the predicate columns.
        sql = sa.text(
            f"""
            WITH cte AS (
                SELECT ctid
                FROM {table_name}
                WHERE {where_sql}
                ORDER BY {order_by}
                LIMIT :limit
                FOR UPDATE
                SKIP LOCKED
            )
            UPDATE {table_name} t
            SET {set_sql}
            FROM cte
            WHERE t.ctid = cte.ctid
            RETURNING 1;
            """
        )
        res = conn.execute(sql, {"limit": batch_size})
        rowcount = res.rowcount or 0
        total += rowcount
        batches += 1
        if rowcount == 0:
            break
        if max_batches is not None and batches >= max_batches:
            break
    return total

