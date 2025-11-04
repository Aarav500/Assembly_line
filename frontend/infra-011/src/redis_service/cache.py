from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Awaitable, Callable, Optional

from redis.asyncio import Redis

from .config import RedisConfig


class CacheService:
    def __init__(self, redis: Redis, config: Optional[RedisConfig] = None, namespace: Optional[str] = None) -> None:
        self.redis = redis
        self.config = config or RedisConfig.from_env()
        self.namespace = namespace or self.config.namespace

    def key(self, *parts: str) -> str:
        safe = [self.namespace, "cache", *[str(p).replace(" ", "_") for p in parts]]
        return ":".join(safe)

    @staticmethod
    def _serialize(value: Any) -> str:
        return json.dumps(value, separators=(",", ":"))

    @staticmethod
    def _deserialize(value: Optional[str]) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    async def get(self, key: str) -> Any:
        raw = await self.redis.get(key)
        return self._deserialize(raw)

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        ttl = ttl_seconds if ttl_seconds is not None else self.config.default_ttl_seconds
        payload = self._serialize(value)
        return await self.redis.set(key, payload, ex=ttl)

    async def delete(self, key: str) -> int:
        return await self.redis.delete(key)

    async def ttl(self, key: str) -> int:
        return await self.redis.ttl(key)

    async def get_or_set(
        self,
        key: str,
        compute: Callable[[], Any | Awaitable[Any]],
        ttl_seconds: Optional[int] = None,
        use_lock: bool = True,
        lock_ttl_seconds: int = 10,
        wait_timeout_seconds: int = 10,
        poll_interval_seconds: float = 0.1,
    ) -> Any:
        existing = await self.get(key)
        if existing is not None:
            return existing

        lock_key = f"{key}:lock"
        lock_acquired = False
        start = time.monotonic()

        if use_lock:
            lock_acquired = await self.redis.set(lock_key, "1", nx=True, ex=lock_ttl_seconds)
            if not lock_acquired:
                # Wait for another worker to populate the cache
                while time.monotonic() - start < wait_timeout_seconds:
                    await asyncio.sleep(poll_interval_seconds)
                    val = await self.get(key)
                    if val is not None:
                        return val
                # Timed out; proceed without lock to compute

        try:
            result = compute()
            if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
                result = await result  # type: ignore[assignment]
            await self.set(key, result, ttl_seconds=ttl_seconds)
            return result
        finally:
            if use_lock and lock_acquired:
                await self.redis.delete(lock_key)

