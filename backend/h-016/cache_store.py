import time
import threading
import hashlib
from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional, Dict


class TTLPolicy(str, Enum):
    FIXED = "fixed"               # absolute expiration from write time
    SLIDING = "sliding"           # renew expiration on each access
    FOREVER = "forever"           # never expires
    STALE_WHILE_REVALIDATE = "stale_while_revalidate"  # serve stale within window, refresh in background


@dataclass
class CacheEntry:
    value: Any
    policy: TTLPolicy
    created_at: float
    last_access: float
    expires_at: Optional[float]
    ttl_seconds: Optional[int] = None
    stale_ttl_seconds: Optional[int] = 0


class InMemoryCache:
    def __init__(self):
        self._data: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._metrics = {
            "set": 0,
            "get": 0,
            "delete": 0,
            "purged": 0,
        }

    def make_key(self, text: str, model: str) -> str:
        h = hashlib.sha256()
        payload = (model + "|" + text).encode("utf-8")
        h.update(payload)
        return h.hexdigest()

    def get_entry(self, key: str) -> Optional[CacheEntry]:
        with self._lock:
            self._metrics["get"] += 1
            return self._data.get(key)

    def set_entry(self, key: str, entry: CacheEntry):
        with self._lock:
            self._data[key] = entry
            self._metrics["set"] += 1

    def delete(self, key: str):
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._metrics["delete"] += 1

    def size(self) -> int:
        with self._lock:
            return len(self._data)

    def _should_remove(self, key: str, entry: CacheEntry, now: float) -> bool:
        # For purge purposes: remove only when entry is beyond any stale window
        if entry.policy == TTLPolicy.FOREVER:
            return False
        if entry.policy == TTLPolicy.STALE_WHILE_REVALIDATE:
            fresh = entry.ttl_seconds or 0
            stale = entry.stale_ttl_seconds or 0
            horizon = entry.created_at + fresh + stale
            return now > horizon
        # For fixed/sliding, remove if expired
        if entry.expires_at is None:
            return False
        return now > entry.expires_at

    def purge_expired(self):
        now = time.time()
        removed = 0
        with self._lock:
            keys = list(self._data.keys())
            for k in keys:
                e = self._data.get(k)
                if e and self._should_remove(k, e, now):
                    del self._data[k]
                    removed += 1
        self._metrics["purged"] += removed
        return removed

    def stats(self):
        return {**self._metrics}

