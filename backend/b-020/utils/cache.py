import time
import threading
from typing import Any, Optional


class TTLCache:
    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if expires_at is not None and now > expires_at:
                # expired
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: int = 600) -> None:
        expires_at = time.time() + ttl if ttl and ttl > 0 else None
        with self._lock:
            self._store[key] = (expires_at, value)

    def clear(self):
        with self._lock:
            self._store.clear()


# Global caches
trends_cache = TTLCache()
news_cache = TTLCache()

