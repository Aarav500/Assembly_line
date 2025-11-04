import time
from functools import wraps
from flask import current_app, request, make_response


class SimpleCache:
    def __init__(self, default_timeout=30):
        self.default_timeout = default_timeout
        self._store = {}

    def _now(self):
        return time.time()

    def set(self, key, value, timeout=None):
        try:
            ttl = timeout if timeout is not None else self.default_timeout
            expire_at = self._now() + ttl
            self._store[key] = (expire_at, value)
        except Exception as e:
            current_app.logger.error(f"Cache set error: {e}")

    def get(self, key):
        try:
            item = self._store.get(key)
            if not item:
                return None
            expire_at, value = item
            if expire_at < self._now():
                self._store.pop(key, None)
                return None
            return value
        except Exception as e:
            current_app.logger.error(f"Cache get error: {e}")
            return None

    def delete(self, key):
        try:
            self._store.pop(key, None)
        except Exception as e:
            current_app.logger.error(f"Cache delete error: {e}")


def register_cache(app, cache: SimpleCache):
    try:
        app.extensions = getattr(app, "extensions", {})
        app.extensions["simple_cache"] = cache
        return cache
    except Exception as e:
        app.logger.error(f"Cache registration error: {e}")
        return None


def cache_response(timeout=60):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                cache = current_app.extensions.get("simple_cache") if hasattr(current_app, "extensions") else None
                if not cache:
                    return fn(*args, **kwargs)
                key = f"resp:{request.method}:{request.full_path}"
                entry = cache.get(key)
                if entry is not None:
                    data = entry["data"]
                    status = entry["status"]
                    headers = entry["headers"]
                    resp = make_response(data, status)
                    for k, v in headers:
                        resp.headers[k] = v
                    resp.headers["X-Cache"] = "HIT"
                    return resp
                resp = make_response(fn(*args, **kwargs))
                cache.set(key, {
                    "data": resp.get_data(),
                    "status": resp.status_code,
                    "headers": list(resp.headers.items()),
                }, timeout=timeout)
                resp.headers["X-Cache"] = "MISS"
                return resp
            except Exception as e:
                current_app.logger.error(f"Cache response error: {e}")
                return fn(*args, **kwargs)
        # tag for feature detection
        tags = getattr(fn, "__feature_tags__", set())
        tags.add("caching")
        wrapper.__feature_tags__ = tags
        wrapper.__uses_caching__ = True
        return wrapper
    return decorator