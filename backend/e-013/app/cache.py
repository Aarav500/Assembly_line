import threading
import time
from typing import Any, Optional

class TTLDict:
    """Thread-safe TTL cache with simple LRU eviction.

    Not as full-featured as cachetools, but no external deps required for Lambda layers.
    """

    def __init__(self, maxsize: int = 10000, default_ttl: int = 60):
        self._store: dict[str, tuple[Any, float]] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()
        self._maxsize = maxsize
        self._default_ttl = default_ttl

    def _evict_if_needed(self):
        while len(self._order) > self._maxsize:
            k = self._order.pop(0)
            self._store.pop(k, None)

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            val, exp = item
            if exp < now:
                # expired
                self._store.pop(key, None)
                try:
                    self._order.remove(key)
                except ValueError:
                    pass
                return None
            # move to end (recently used)
            try:
                self._order.remove(key)
            except ValueError:
                pass
            self._order.append(key)
            return val

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        exp = time.time() + (ttl if ttl is not None else self._default_ttl)
        with self._lock:
            self._store[key] = (value, exp)
            try:
                self._order.remove(key)
            except ValueError:
                pass
            self._order.append(key)
            self._evict_if_needed()

    def __setitem__(self, key: str, value: Any):
        self.set(key, value, None)

edge_cache = TTLDict(maxsize=10000, default_ttl=60)

