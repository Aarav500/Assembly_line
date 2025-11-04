import hashlib
import json
import time
from typing import Iterable, Optional, Sequence

import redis

import config

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(config.REDIS_URL, decode_responses=True)
    return _pool


def get_redis():
    return redis.Redis(connection_pool=_get_pool())


def namespaced(key: str) -> str:
    return f"{config.CACHE_NAMESPACE}:{key}"


def key_for(route: str, *parts: Sequence[str]) -> str:
    suffix = ":".join(str(p) for p in parts)
    return namespaced(f"{route}:{suffix}") if suffix else namespaced(route)


def compute_etag(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def set_cache(key: str, value: str, ttl: int, tags: Optional[Iterable[str]] = None):
    r = get_redis()
    r.setex(key, ttl, value)
    if tags:
        for tag in tags:
            r.sadd(namespaced(f"tag:{tag}"), key)


def get_cache(key: str) -> Optional[str]:
    return get_redis().get(key)


def touch_cache(key: str, ttl: Optional[int] = None):
    if ttl is None:
        ttl = config.DEFAULT_TTL
    get_redis().expire(key, ttl)


def invalidate_keys(keys: Iterable[str]) -> int:
    if not keys:
        return 0
    keys = list(keys)
    if not keys:
        return 0
    return get_redis().delete(*keys)


def invalidate_tags(tags: Iterable[str]) -> int:
    r = get_redis()
    total = 0
    for tag in set(tags):
        tagkey = namespaced(f"tag:{tag}")
        members = r.smembers(tagkey)
        if members:
            total += r.delete(*members)
        r.delete(tagkey)
    return total


def cache_entry(payload_obj: dict, extra_headers: Optional[dict] = None, tags: Optional[Iterable[str]] = None, ttl: Optional[int] = None):
    if ttl is None:
        ttl = config.DEFAULT_TTL
    payload_str = json.dumps(payload_obj, separators=(",", ":"), sort_keys=True)
    etag = compute_etag(payload_str)
    last_modified = int(time.time())
    headers = {
        "ETag": etag,
        "Last-Modified": str(last_modified),
    }
    if extra_headers:
        headers.update(extra_headers)
    return payload_str, headers, tags or [], ttl

