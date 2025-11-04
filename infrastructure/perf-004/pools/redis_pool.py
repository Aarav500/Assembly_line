from typing import Optional

from flask import current_app
from redis import Redis
from redis.connection import ConnectionPool


def init_redis(app):
    url = app.config.get("REDIS_URL")
    max_conn = app.config.get("REDIS_MAX_CONNECTIONS", 20)
    pool = ConnectionPool.from_url(url, max_connections=max_conn, decode_responses=True)
    client = Redis(connection_pool=pool)
    app.extensions["redis_pool"] = pool
    app.extensions["redis_client"] = client


def shutdown_redis(app):
    pool: Optional[ConnectionPool] = app.extensions.get("redis_pool")
    if pool:
        try:
            pool.disconnect()
        except Exception:
            pass


def get_redis() -> Redis:
    client: Optional[Redis] = current_app.extensions.get("redis_client")
    if client is None:
        raise RuntimeError("Redis not initialized")
    return client


def ping_redis(timeout: float = 1.0) -> bool:
    try:
        client = get_redis()
        return bool(client.ping())
    except Exception:
        return False

