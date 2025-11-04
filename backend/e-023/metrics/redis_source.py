import os
import redis

from .base import MetricsSource


class RedisMetrics(MetricsSource):
    def __init__(self, redis_url: str = None, db: int = None, key_type: str = 'list'):
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.db = db
        self.key_type = key_type
        self._client = redis.Redis.from_url(self.redis_url, db=self.db)

    def get_queue_depth(self, metric_id: str) -> int:
        key = metric_id
        if self.key_type == 'list':
            return int(self._client.llen(key))
        if self.key_type == 'stream':
            return int(self._client.xlen(key))
        if self.key_type == 'zset':
            return int(self._client.zcard(key))
        if self.key_type == 'set':
            return int(self._client.scard(key))
        if self.key_type == 'hash':
            return int(self._client.hlen(key))
        # default: exists -> 1 or 0
        return 1 if self._client.exists(key) else 0

