from redis import Redis
from redis.asyncio import Redis as AsyncRedis  # for future use if needed
from urllib.parse import urlparse
from typing import Optional
from config import settings


_redis_instance: Optional[Redis] = None


def get_redis() -> Redis:
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_instance

