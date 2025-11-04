from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Optional

from redis.asyncio import Redis

from .config import RedisConfig


class PubSubService:
    def __init__(self, redis: Redis, config: Optional[RedisConfig] = None, namespace: Optional[str] = None) -> None:
        self.redis = redis
        self.config = config or RedisConfig.from_env()
        self.namespace = namespace or self.config.namespace

    def channel(self, name: str) -> str:
        return f"{self.namespace}:pubsub:{name}"

    async def publish(self, channel: str, message: Any) -> int:
        if not isinstance(message, str):
            payload = json.dumps(message, separators=(",", ":"))
        else:
            payload = message
        return await self.redis.publish(channel, payload)

    async def subscribe(self, channel: str, *, ignore_own_messages: bool = False) -> AsyncIterator[Any]:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for item in pubsub.listen():
                if item is None:
                    await asyncio.sleep(0.01)
                    continue
                if item.get("type") != "message":
                    continue
                data = item.get("data")
                try:
                    yield json.loads(data)  # type: ignore[arg-type]
                except Exception:
                    yield data
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

