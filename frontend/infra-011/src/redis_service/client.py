from __future__ import annotations

import asyncio
from typing import Optional

from redis.asyncio import Redis

from .config import RedisConfig

__all__ = ["init_redis", "get_redis", "close_redis"]

_redis_client: Optional[Redis] = None
_redis_lock = asyncio.Lock()
_config: Optional[RedisConfig] = None


async def init_redis(config: Optional[RedisConfig] = None) -> Redis:
    global _redis_client, _config
    async with _redis_lock:
        if _redis_client is None:
            _config = config or RedisConfig.from_env()
            _redis_client = Redis.from_url(_config.redis_url, decode_responses=True)
        return _redis_client


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        await init_redis()
    assert _redis_client is not None
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    async with _redis_lock:
        if _redis_client is not None:
            try:
                await _redis_client.aclose()
            finally:
                _redis_client = None

