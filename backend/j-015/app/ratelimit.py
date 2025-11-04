import time
from collections import defaultdict, deque
from flask import request, current_app, jsonify


class RateLimiter:
    def __init__(self, limit_per_window: int = 100, window_seconds: int = 900, key_func=None):
        self.limit = int(limit_per_window)
        self.window = int(window_seconds)
        self.key_func = key_func or (lambda: ())
        self._buckets = defaultdict(deque)

    def _key(self):
        # per IP + path + custom key tuple
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "-").split(",")[0].strip()
        path = request.path
        extra = self.key_func() if self.key_func else ()
        return (ip, path) + tuple(extra)

    def check(self):
        # Skip rate limit for static files
        if request.path.startswith("/static/"):
            return None

        now = time.time()
        key = self._key()
        q = self._buckets[key]

        # purge old entries
        cutoff = now - self.window
        while q and q[0] < cutoff:
            q.popleft()

        if len(q) >= self.limit:
            retry_after = max(1, int(q[0] + self.window - now))
            resp = jsonify({
                "error": "rate_limited",
                "message": "Too many requests. Please try again later.",
                "retry_after_seconds": retry_after,
            })
            resp.status_code = 429
            resp.headers["Retry-After"] = str(retry_after)
            return resp

        q.append(now)
        return None

