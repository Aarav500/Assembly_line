import json
import os
import threading
import time

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None


class Cache:
    def __init__(self, config):
        self.config = config
        self.client = None
        self.backend = "memory"
        self.is_redis = False

        url = getattr(config, "REDIS_URL", None)
        if url and redis is not None:
            try:
                self.client = redis.Redis.from_url(url, decode_responses=True)
                # Validate connectivity
                self.client.ping()
                self.backend = "redis"
                self.is_redis = True
            except Exception:
                # Fallback to memory if redis unreachable
                self.client = None
                self.backend = "memory"
                self.is_redis = False

        if not self.client:
            self._store = {}
            self._lock = threading.RLock()

    # General KV operations
    def get(self, key):
        if self.is_redis:
            return self.client.get(key)
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            value, exp = entry
            if exp is not None and now >= exp:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key, value, ttl=None):
        if self.is_redis:
            if ttl:
                return self.client.set(key, value, ex=int(ttl))
            else:
                return self.client.set(key, value)
        exp = None if ttl is None else time.time() + int(ttl)
        with self._lock:
            self._store[key] = (value, exp)
            return True

    def setnx(self, key, value, ttl=None):
        if self.is_redis:
            # SET with NX and expiration
            return bool(self.client.set(key, value, nx=True, ex=int(ttl) if ttl else None))
        exp = None if ttl is None else time.time() + int(ttl)
        with self._lock:
            if key in self._store:
                # Check expiry
                val, ex = self._store[key]
                if ex is not None and time.time() >= ex:
                    # expired, replace
                    self._store[key] = (value, exp)
                    return True
                return False
            self._store[key] = (value, exp)
            return True

    def delete(self, key):
        if self.is_redis:
            return self.client.delete(key)
        with self._lock:
            return 1 if self._store.pop(key, None) is not None else 0

    def exists(self, key):
        if self.is_redis:
            return bool(self.client.exists(key))
        return self.get(key) is not None

    def ttl(self, key):
        if self.is_redis:
            t = self.client.ttl(key)
            return int(t) if t is not None and t >= 0 else None
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            _, exp = entry
            if exp is None:
                return None
            remaining = int(exp - time.time())
            return max(remaining, 0)

    # JSON helpers
    def get_json(self, key):
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def set_json(self, key, obj, ttl=None):
        raw = json.dumps(obj, separators=(",", ":"))
        return self.set(key, raw, ttl=ttl)

