import threading
import time
from typing import Callable, Dict, Iterable, Optional, Tuple

from .redis_cache import RedisCache


class CacheWarmer:
    """
    Periodically warms cache for popular or preconfigured keys.

    - Uses a distributed lock to avoid multiple instances warming simultaneously.
    - You can provide a registry mapping base_key -> (loader, ttl, tags)
    - Also warms by popularity list from Redis (top N), optionally if a loader registry
      contains a matching loader for that base key prefix or exact key.
    """

    def __init__(
        self,
        cache: RedisCache,
        interval_seconds: int = 60,
        top_n: int = 100,
        loader_registry: Optional[Dict[str, Tuple[Callable[[], object], int, Optional[Iterable[str]]]]] = None,
    ) -> None:
        self.cache = cache
        self.interval = int(interval_seconds)
        self.top_n = int(top_n)
        self.loader_registry = loader_registry or {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def warm_keys(self, keys: Iterable[str]) -> None:
        for key in keys:
            self._warm_key_if_possible(key)

    def _run_loop(self) -> None:
        lock_key = f"cache:{self.cache.ns}:warm-lock"
        r = self.cache.r
        while not self._stop.is_set():
            lock = r.lock(lock_key, timeout=self.interval - 1 if self.interval > 1 else 1, blocking_timeout=0)
            acquired = False
            try:
                acquired = lock.acquire(blocking=False)
            except Exception:
                acquired = False
            if acquired:
                try:
                    # Warm preconfigured registry keys first
                    for base_key, (loader, ttl, tags) in list(self.loader_registry.items()):
                        try:
                            self.cache.get_or_set(base_key, loader=loader, ttl=ttl, tags=tags)
                        except Exception:
                            pass
                    # Warm top N popular keys if loader is known
                    top = self.cache.top_keys(self.top_n)
                    for base_key, _score in top:
                        self._warm_key_if_possible(base_key)
                finally:
                    try:
                        lock.release()
                    except Exception:
                        pass
            # Sleep interval
            self._stop.wait(self.interval)

    def _warm_key_if_possible(self, base_key: str) -> None:
        # exact match
        entry = self.loader_registry.get(base_key)
        if entry:
            loader, ttl, tags = entry
            try:
                self.cache.get_or_set(base_key, loader=loader, ttl=ttl, tags=tags)
            except Exception:
                pass
            return
        # prefix match
        for prefix, (loader, ttl, tags) in self.loader_registry.items():
            if prefix.endswith('*') and base_key.startswith(prefix[:-1]):
                try:
                    self.cache.get_or_set(base_key, loader=loader, ttl=ttl, tags=tags)
                except Exception:
                    pass
                return

