from __future__ import annotations

import json
import secrets
from typing import Any, Dict, Optional

from redis.asyncio import Redis

from .config import RedisConfig


class SessionStore:
    def __init__(self, redis: Redis, config: Optional[RedisConfig] = None, namespace: Optional[str] = None) -> None:
        self.redis = redis
        self.config = config or RedisConfig.from_env()
        self.namespace = namespace or self.config.namespace

    def key(self, session_id: str) -> str:
        return f"{self.namespace}:session:{session_id}"

    async def create_session(
        self,
        user_id: str,
        data: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> str:
        session_id = secrets.token_urlsafe(32)
        k = self.key(session_id)
        payload = {
            "user_id": user_id,
            "data": data or {},
        }
        ttl = ttl_seconds if ttl_seconds is not None else self.config.default_ttl_seconds
        await self.redis.set(k, json.dumps(payload, separators=(",", ":")), ex=ttl)
        return session_id

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        k = self.key(session_id)
        raw = await self.redis.get(k)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        k = self.key(session_id)
        sess = await self.get_session(session_id)
        if not sess:
            return False
        sess["data"] = data
        ttl = await self.redis.ttl(k)
        if ttl and ttl > 0:
            return await self.redis.set(k, json.dumps(sess, separators=(",", ":")), ex=ttl)
        else:
            return await self.redis.set(k, json.dumps(sess, separators=(",", ":")))

    async def renew_session(self, session_id: str, ttl_seconds: Optional[int] = None) -> bool:
        k = self.key(session_id)
        ttl = ttl_seconds if ttl_seconds is not None else self.config.default_ttl_seconds
        return await self.redis.expire(k, ttl)

    async def destroy_session(self, session_id: str) -> int:
        k = self.key(session_id)
        return await self.redis.delete(k)

