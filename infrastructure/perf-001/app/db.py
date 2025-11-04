import contextlib
import psycopg2
import psycopg2.extras
from .config import Config


def get_connection(cfg: Config):
    conn = psycopg2.connect(dsn=cfg.dsn())
    conn.autocommit = True
    if cfg.enable_pg_stat_statements_setup:
        with contextlib.suppress(Exception):
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
    return conn


def set_statement_timeout(conn, ms: int | None):
    if ms is None:
        return
    with conn.cursor() as cur:
        cur.execute("SET lock_timeout = '0'" )
        cur.execute("SET idle_in_transaction_session_timeout = '0'")
        cur.execute(f"SET statement_timeout = '{int(ms)}ms'")


def reset_statement_timeout(conn):
    with conn.cursor() as cur:
        cur.execute("RESET statement_timeout")


def fetchall_dicts(cur):
    cols = [desc[0] for desc in cur.description]
    for row in cur.fetchall():
        yield {k: v for k, v in zip(cols, row)}

