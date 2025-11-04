import time
from flask import request, abort, g
import logging

logger = logging.getLogger(__name__)


class SimpleRateLimiter:
    def __init__(self, limit=100, window=60, key_func=None):
        self.limit = int(limit)
        self.window = int(window)
        self.key_func = key_func or (lambda: request.remote_addr or "anonymous")
        # Store counters as {key: {bucket_start: count}}
        self._counters = {}

    def _bucket_start(self, now):
        return int(now // self.window) * self.window

    def hit(self):
        try:
            now = time.time()
            key = self.key_func()
            bucket = self._bucket_start(now)
            store = self._counters.setdefault(key, {})
            # Cleanup old buckets for the key
            for b in list(store.keys()):
                if b < bucket:
                    store.pop(b, None)
            count = store.get(bucket, 0) + 1
            store[bucket] = count
            remaining = max(self.limit - count, 0)
            reset = bucket + self.window
            return count, remaining, reset
        except Exception as e:
            logger.error(f"Error in rate limiter hit: {e}")
            # Return safe defaults to allow request through
            return 0, self.limit, int(time.time()) + self.window

    def is_limited(self):
        try:
            count, remaining, reset = self.hit()
            return count > self.limit, remaining, reset
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            # Fail open - don't block on error
            return False, self.limit, int(time.time()) + self.window


def register_rate_limiter(app, limiter: SimpleRateLimiter):
    try:
        app.extensions = getattr(app, "extensions", {})
        app.extensions["rate_limiter"] = limiter

        @app.before_request
        def _rate_limit_before_request():
            try:
                limited, remaining, reset = limiter.is_limited()
                g.rate_limit = {
                    "limit": limiter.limit,
                    "remaining": remaining,
                    "reset": reset,
                }
                if limited:
                    abort(429, description="Rate limit exceeded")
            except Exception as e:
                logger.error(f"Error in rate limit before_request: {e}")
                # Fail open - allow request to proceed

        @app.after_request
        def _rate_limit_after_request(response):
            try:
                rl = getattr(g, "rate_limit", None)
                if rl:
                    response.headers["X-RateLimit-Limit"] = str(rl["limit"])
                    response.headers["X-RateLimit-Remaining"] = str(rl["remaining"])
                    response.headers["X-RateLimit-Reset"] = str(int(rl["reset"]))
            except Exception as e:
                logger.error(f"Error in rate limit after_request: {e}")
            return response

        return limiter
    except Exception as e:
        logger.error(f"Error registering rate limiter: {e}")
        raise