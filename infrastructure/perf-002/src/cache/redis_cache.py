import json
import pickle
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import redis

from .config import (
    REDIS_URL,
    CACHE_NAMESPACE,
    CACHE_DEFAULT_TTL,
    CACHE_REFRESH_AHEAD_SECONDS,
    CACHE_ENABLE_PUBSUB,
)


class RedisCache:
    """
    Redis-backed caching layer with:
    - Read-through and write-through helpers
    - Tag-based intelligent invalidation via generational versioning
    - Cache stampede protection with distributed locks
    - Popularity tracking and cache warming integration
    - Hit/miss metrics stored in Redis
    - Optional refresh-ahead near expiry
    """

    def __init__(
        self,
        redis_url: str = REDIS_URL,
        namespace: str = CACHE_NAMESPACE,
        default_ttl: int = CACHE_DEFAULT_TTL,
        refresh_ahead_seconds: int = CACHE_REFRESH_AHEAD_SECONDS,
        enable_pubsub: bool = CACHE_ENABLE_PUBSUB,
    ) -> None:
        self.r = redis.Redis.from_url(redis_url, decode_responses=False)
        self.ns = namespace
        self.default_ttl = int(default_ttl)
        self.refresh_ahead_seconds = int(refresh_ahead_seconds)
        self.enable_pubsub = enable_pubsub

        self._metrics_key = f"cache:{self.ns}:metrics"
        self._tag_versions_key = f"cache:{self.ns}:tag_versions"
        self._popularity_key = f"cache:{self.ns}:popularity"
        self._events_channel = f"cache:{self.ns}:events"

        # Register Lua script to fetch tag versions with default=1
        self._lua_get_tag_versions = self.r.register_script(
            """
            local key = KEYS[1]
            local res = {}
            for i=1,#ARGV do
                local tag = ARGV[i]
                local v = redis.call('HGET', key, tag)
                if not v then
                    redis.call('HSETNX', key, tag, 1)
                    v = '1'
                end
                table.insert(res, v)
            end
            return res
            """
        )

    # ------------- Public API -------------

    def get(
        self,
        base_key: str,
        tags: Optional[Iterable[str]] = None,
    ) -> Any:
        """Get a value from cache. Returns None if not found."""
        raw_key = self._compose_key(base_key, tags)
        self._inc_popularity(base_key)
        val = self.r.get(raw_key)
        if val is None:
            self._metric_incr("misses", 1)
            return None
        self._metric_incr("hits", 1)
        try:
            return pickle.loads(val)
        except Exception:
            # Corrupted payload; delete and treat as miss
            self.r.delete(raw_key)
            self._metric_incr("misses", 1)
            return None

    def set(
        self,
        base_key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> None:
        raw_key = self._compose_key(base_key, tags)
        payload = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        ttl = int(ttl or self.default_ttl)
        self.r.setex(raw_key, ttl, payload)
        self._metric_incr("sets", 1)

    def delete(self, base_key: str, tags: Optional[Iterable[str]] = None) -> int:
        raw_key = self._compose_key(base_key, tags)
        deleted = self.r.delete(raw_key)
        if deleted:
            self._metric_incr("deletes", int(deleted))
        return int(deleted)

    def get_or_set(
        self,
        base_key: str,
        loader: Callable[[], Any],
        ttl: Optional[int] = None,
        tags: Optional[Iterable[str]] = None,
        refresh: bool = False,
        lock_timeout: int = 10,
        wait_timeout: int = 5,
        allow_fallback_load: bool = True,
    ) -> Any:
        """
        Read-through cache helper with stampede protection. If refresh=True, it forces
        recompute and cache set under a lock.
        """
        ttl_val = int(ttl or self.default_ttl)
        raw_key = self._compose_key(base_key, tags)
        self._inc_popularity(base_key)

        if not refresh:
            cached = self.r.get(raw_key)
            if cached is not None:
                self._metric_incr("hits", 1)
                obj = None
                try:
                    obj = pickle.loads(cached)
                except Exception:
                    obj = None
                    self.r.delete(raw_key)
                    self._metric_incr("misses", 1)
                # Refresh-ahead
                if obj is not None and self.refresh_ahead_seconds > 0:
                    self._maybe_refresh_ahead(base_key, loader, ttl_val, tags, raw_key)
                if obj is not None:
                    return obj
            else:
                self._metric_incr("misses", 1)

        lock_key = self._lock_key(raw_key)
        lock = self.r.lock(lock_key, timeout=lock_timeout, blocking_timeout=wait_timeout)
        acquired = False
        try:
            acquired = lock.acquire(blocking=True)
        except Exception:
            acquired = False

        if acquired:
            try:
                # Double-check after acquiring lock (another worker may have set it)
                if not refresh:
                    cached2 = self.r.get(raw_key)
                    if cached2 is not None:
                        try:
                            return pickle.loads(cached2)
                        finally:
                            pass
                # Compute and set
                value = loader()
                payload = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
                self.r.setex(raw_key, ttl_val, payload)
                self._metric_incr("sets", 1)
                self._metric_incr("stampede_loads", 1)
                return value
            finally:
                try:
                    lock.release()
                except Exception:
                    pass
        else:
            # Didn't get the lock; waiters will see the value soon. Try to read again.
            val = self.r.get(raw_key)
            if val is not None:
                try:
                    return pickle.loads(val)
                except Exception:
                    self.r.delete(raw_key)
            # Optionally compute as fallback (best-effort)
            if allow_fallback_load:
                value = loader()
                # Try to set with NX to avoid overwriting the rightful lock holder's value
                payload = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
                # TTL set if setnx OK; otherwise ignore
                was_set = self.r.set(raw_key, payload, ex=ttl_val, nx=True)
                if was_set:
                    self._metric_incr("sets", 1)
                return value
            return None

    def invalidate_tags(self, tags: Iterable[str]) -> None:
        tags = list(tags) if tags else []
        if not tags:
            return
        pipe = self.r.pipeline()
        for t in tags:
            pipe.hincrby(self._tag_versions_key, t, 1)
        pipe.execute()
        self._metric_incr("invalidations", 1)
        if self.enable_pubsub:
            try:
                event = {"type": "invalidate_tags", "tags": list(tags), "ts": time.time()}
                self.r.publish(self._events_channel, json.dumps(event).encode("utf-8"))
            except Exception:
                pass

    def invalidate_prefix(self, prefix: str, batch_size: int = 500) -> int:
        """
        Pattern-based invalidation. Beware: SCAN may be expensive in large keyspaces.
        Returns number of keys deleted.
        """
        pattern = f"cache:{self.ns}:data:{prefix}*"
        cursor = 0
        total = 0
        while True:
            cursor, keys = self.r.scan(cursor=cursor, match=pattern, count=batch_size)
            if keys:
                total += int(self.r.delete(*keys))
            if cursor == 0:
                break
        if total:
            self._metric_incr("deletes", total)
        return total

    def top_keys(self, n: int = 100) -> List[Tuple[str, float]]:
        res = self.r.zrevrange(self._popularity_key, 0, n - 1, withscores=True)
        out: List[Tuple[str, float]] = []
        for k, score in res:
            try:
                out.append((k.decode("utf-8"), float(score)))
            except Exception:
                continue
        return out

    def get_metrics(self) -> Dict[str, int]:
        raw = self.r.hgetall(self._metrics_key)
        metrics: Dict[str, int] = {}
        for k, v in raw.items():
            key = k.decode("utf-8") if isinstance(k, (bytes, bytearray)) else str(k)
            try:
                metrics[key] = int(v)
            except Exception:
                metrics[key] = 0
        return metrics

    # ------------- Internal helpers -------------

    def _compose_key(self, base_key: str, tags: Optional[Iterable[str]]) -> str:
        if not tags:
            return f"cache:{self.ns}:data:{base_key}"
        tag_list = list(tags)
        versions = self._get_tag_versions(tag_list)
        parts = [f"{t}={versions[t]}" for t in sorted(tag_list)]
        suffix = "|".join(parts)
        return f"cache:{self.ns}:data:{base_key}|{suffix}"

    def _get_tag_versions(self, tags: List[str]) -> Dict[str, int]:
        if not tags:
            return {}
        res = self._lua_get_tag_versions(keys=[self._tag_versions_key], args=tags)
        out: Dict[str, int] = {}
        for t, v in zip(tags, res):
            if isinstance(v, (bytes, bytearray)):
                v = v.decode("utf-8")
            out[t] = int(v)
        return out

    def _lock_key(self, raw_key: str) -> str:
        return f"lock:{raw_key}"

    def _metric_incr(self, field: str, amount: int = 1) -> None:
        try:
            self.r.hincrby(self._metrics_key, field, amount)
        except Exception:
            pass

    def _inc_popularity(self, base_key: str) -> None:
        try:
            self.r.zincrby(self._popularity_key, 1.0, base_key)
        except Exception:
            pass

    def _maybe_refresh_ahead(
        self,
        base_key: str,
        loader: Callable[[], Any],
        ttl: int,
        tags: Optional[Iterable[str]],
        raw_key: str,
    ) -> None:
        try:
            ttl_left = self.r.ttl(raw_key)
            if ttl_left is None:
                return
            # ttl_left: -2 no exist, -1 no expire, >=0 seconds
            if ttl_left > 0 and ttl_left <= self.refresh_ahead_seconds:
                # Spawn background refresh if lock is available
                t = threading.Thread(
                    target=self._background_refresh,
                    args=(base_key, loader, ttl, tags, raw_key),
                    daemon=True,
                )
                t.start()
        except Exception:
            pass

    def _background_refresh(
        self,
        base_key: str,
        loader: Callable[[], Any],
        ttl: int,
        tags: Optional[Iterable[str]],
        raw_key: str,
    ) -> None:
        lock_key = self._lock_key(raw_key)
        lock = self.r.lock(lock_key, timeout=10, blocking_timeout=0)
        try:
            if lock.acquire(blocking=False):
                try:
                    value = loader()
                    payload = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
                    self.r.setex(raw_key, ttl, payload)
                    self._metric_incr("sets", 1)
                finally:
                    try:
                        lock.release()
                    except Exception:
                        pass
        except Exception:
            pass

