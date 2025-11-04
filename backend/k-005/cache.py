import time
from collections import OrderedDict
from typing import Any

class ResponseCache:
    def __init__(self, ttl_seconds: int = 300, max_entries: int = 2048):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self.store = OrderedDict()

    def _purge_expired(self):
        now = time.time()
        keys_to_delete = []
        for k, (v, ts) in list(self.store.items()):
            if now - ts > self.ttl:
                keys_to_delete.append(k)
        for k in keys_to_delete:
            self.store.pop(k, None)

    def get(self, key: str) -> Any:
        self._purge_expired()
        if key in self.store:
            v, ts = self.store.pop(key)
            # reinsert to update LRU order
            self.store[key] = (v, ts)
            return v
        return None

    def set(self, key: str, value: Any):
        self._purge_expired()
        if key in self.store:
            self.store.pop(key, None)
        self.store[key] = (value, time.time())
        while len(self.store) > self.max_entries:
            self.store.popitem(last=False)

