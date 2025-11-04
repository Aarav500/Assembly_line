import time
from collections import OrderedDict
from typing import Any, Optional


class TTLCache:
    def __init__(self, maxsize: int = 10000, ttl_seconds: int = 3600) -> None:
        self.maxsize = maxsize
        self.ttl = ttl_seconds
        self._store: "OrderedDict[str, float]" = OrderedDict()

    def _expire(self) -> None:
        now = time.time()
        keys_to_delete = []
        for k, expiry in self._store.items():
            if expiry <= now:
                keys_to_delete.append(k)
            else:
                break  # Ordered by insertion; we only evict expired at head
        for k in keys_to_delete:
            self._store.pop(k, None)

    def add_if_new(self, key: str) -> bool:
        """Returns True if key was new and added; False if it already exists (not expired)."""
        self._expire()
        if key in self._store:
            # refresh order but keep same expiry
            expiry = self._store.pop(key)
            self._store[key] = expiry
            return False
        # evict if necessary
        if len(self._store) >= self.maxsize:
            self._store.popitem(last=False)
        self._store[key] = time.time() + self.ttl
        return True

    def __len__(self) -> int:
        self._expire()
        return len(self._store)

