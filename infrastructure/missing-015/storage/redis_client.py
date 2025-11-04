import redis
import threading
import os

_pool = None
_pool_lock = threading.Lock()


def get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                _pool = redis.ConnectionPool.from_url(url, decode_responses=True)
    return _pool


def get_redis():
    return redis.Redis(connection_pool=get_pool())

