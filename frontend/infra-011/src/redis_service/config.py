from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RedisConfig:
    redis_url: str = "redis://localhost:6379/0"
    namespace: str = "app"
    default_ttl_seconds: int = 3600

    @classmethod
    def from_env(cls) -> "RedisConfig":
        return cls(
            redis_url=os.getenv("REDIS_URL", cls.redis_url),
            namespace=os.getenv("APP_NAMESPACE", cls.namespace),
            default_ttl_seconds=int(os.getenv("DEFAULT_TTL_SECONDS", str(cls.default_ttl_seconds))),
        )

