import os
import random
import threading
import time
from typing import Dict, Iterable, Optional

from cache.redis_cache import RedisCache
from cache.warmup import CacheWarmer
from cache.monitor_server import start_monitor_server
from cache.config import (
    CACHE_NAMESPACE,
    CACHE_DEFAULT_TTL,
    CACHE_REFRESH_AHEAD_SECONDS,
    CACHE_WARMER_INTERVAL,
    CACHE_WARMER_TOPN,
)

# Simulated data source (e.g., database)
_FAKE_DB: Dict[str, Dict] = {
    f"product:{i}": {"id": i, "name": f"Product {i}", "price": round(random.uniform(5, 200), 2)}
    for i in range(1, 501)
}


def load_product(base_key: str):
    # Simulate IO latency
    time.sleep(0.05)
    return _FAKE_DB.get(base_key)


def make_loader(base_key: str):
    return lambda: load_product(base_key)


def main():
    cache = RedisCache(
        namespace=CACHE_NAMESPACE,
        default_ttl=CACHE_DEFAULT_TTL,
        refresh_ahead_seconds=CACHE_REFRESH_AHEAD_SECONDS,
    )

    # Start metrics server
    start_monitor_server()

    # Configure warmer: warm top popular keys and preconfigured prefixes
    registry = {
        "product:*": (lambda: None, 300, None),  # prefix loader resolved below per key
    }

    # Wrap registry to resolve real loader per base key
    resolved_registry = {}
    for k, (ldr, ttl, tags) in registry.items():
        if k.endswith("*"):
            # keep as prefix entry to be resolved in warmer
            resolved_registry[k] = (lambda: None, ttl, tags)
        else:
            resolved_registry[k] = (make_loader(k), ttl, tags)

    warmer = CacheWarmer(cache, interval_seconds=CACHE_WARMER_INTERVAL, top_n=CACHE_WARMER_TOPN, loader_registry=resolved_registry)

    # Patch warmer to resolve prefix loaders at runtime
    def _resolve_loader(base_key: str):
        return make_loader(base_key)

    orig_warm_key_if_possible = warmer._warm_key_if_possible

    def patched_warm_key_if_possible(base_key: str):
        entry = warmer.loader_registry.get(base_key)
        if entry and entry[0] is not None:
            return orig_warm_key_if_possible(base_key)
        # handle prefixes
        for prefix, (loader, ttl, tags) in warmer.loader_registry.items():
            if prefix.endswith('*') and base_key.startswith(prefix[:-1]):
                try:
                    cache.get_or_set(base_key, loader=_resolve_loader(base_key), ttl=ttl, tags=tags)
                except Exception:
                    pass
                return
        # No loader known
        return

    warmer._warm_key_if_possible = patched_warm_key_if_possible  # type: ignore
    warmer.start()

    # Demo workload: random reads and occasional invalidations
    tags_for_products = lambda pid: [f"product:{pid}"]

    def reader_thread():
        while True:
            pid = random.randint(1, 500)
            base_key = f"product:{pid}"
            # read-through with stampede protection
            value = cache.get_or_set(base_key, loader=make_loader(base_key), ttl=300, tags=tags_for_products(pid))
            # Simulate mixed access
            time.sleep(random.uniform(0.005, 0.02))

    def writer_thread():
        while True:
            # Periodically update a random product and invalidate its tag
            pid = random.randint(1, 500)
            base_key = f"product:{pid}"
            # Update the fake DB
            _FAKE_DB[base_key]["price"] = round(random.uniform(5, 200), 2)
            # Invalidate tag to bump version so all keys with that tag will miss
            cache.invalidate_tags(tags_for_products(pid))
            time.sleep(1.5)

    for _ in range(4):
        threading.Thread(target=reader_thread, daemon=True).start()
    threading.Thread(target=writer_thread, daemon=True).start()

    # Keep main alive
    print("Cache demo running. Metrics on /metrics. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

