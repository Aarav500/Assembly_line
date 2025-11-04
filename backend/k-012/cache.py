import time
from threading import RLock
from typing import Any, Dict, Optional


class InMemoryTenantCache:
    def __init__(self):
        self._store: Dict[int, Dict[str, Any]] = {}
        self._expirations: Dict[int, Dict[str, float]] = {}
        self._lock = RLock()

    def _ensure_org(self, org_id: int):
        if org_id not in self._store:
            self._store[org_id] = {}
            self._expirations[org_id] = {}

    def set(self, org_id: int, key: str, value: Any, ttl_seconds: Optional[int] = None):
        with self._lock:
            self._ensure_org(org_id)
            self._store[org_id][key] = value
            if ttl_seconds is not None:
                self._expirations[org_id][key] = time.time() + ttl_seconds
            elif key in self._expirations[org_id]:
                del self._expirations[org_id][key]

    def get(self, org_id: int, key: str) -> Optional[Any]:
        with self._lock:
            if org_id not in self._store or key not in self._store[org_id]:
                return None
            exp = self._expirations[org_id].get(key)
            if exp is not None and time.time() > exp:
                # expired
                del self._store[org_id][key]
                del self._expirations[org_id][key]
                return None
            return self._store[org_id][key]

    def delete(self, org_id: int, key: str):
        with self._lock:
            if org_id in self._store and key in self._store[org_id]:
                del self._store[org_id][key]
            if org_id in self._expirations and key in self._expirations[org_id]:
                del self._expirations[org_id][key]

    def clear_org(self, org_id: int):
        with self._lock:
            if org_id in self._store:
                self._store[org_id].clear()
            if org_id in self._expirations:
                self._expirations[org_id].clear()


tenant_cache = InMemoryTenantCache()

