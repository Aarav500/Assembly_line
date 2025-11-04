from contextlib import contextmanager
from typing import Iterator
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import register_uuid, Json
import uuid

from .config import config

_pool: ThreadedConnectionPool | None = None


def init_pool(minconn: int = 1, maxconn: int = 10) -> None:
    global _pool
    if _pool is None:
        register_uuid()
        _pool = ThreadedConnectionPool(minconn, maxconn, dsn=config.DATABASE_URL)


@contextmanager
def get_conn():
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


def adapt_json(obj):
    return Json(obj)


