from typing import List, Dict
from .db import fetchall_dicts


def get_slow_queries(conn, limit: int = 20, min_mean_ms: int = 50, min_calls: int = 5, order_by: str = "mean_time") -> List[Dict]:
    order_by = order_by.lower()
    if order_by not in {"mean_time", "total_time", "calls"}:
        order_by = "mean_time"
    sql = f"""
    SELECT
      queryid,
      calls,
      total_time,
      mean_time,
      rows,
      shared_blks_hit,
      shared_blks_read,
      shared_blks_dirtied,
      shared_blks_written,
      local_blks_hit,
      local_blks_read,
      temp_blks_read,
      temp_blks_written,
      blk_read_time,
      blk_write_time,
      query
    FROM pg_stat_statements
    WHERE mean_time >= %s AND calls >= %s
    ORDER BY {order_by} DESC
    LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (float(min_mean_ms), int(min_calls), int(limit)))
        return list(fetchall_dicts(cur))

