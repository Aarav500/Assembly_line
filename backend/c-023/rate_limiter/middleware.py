import re
import time
import threading
from typing import Callable, Optional, Tuple, Dict, Any, Union

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None

from flask import request, g, current_app
from functools import wraps


# ----------------------------
# Utilities
# ----------------------------

_UNITS = {
    "s": 1,
    "sec": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
}


def parse_rate(value: str) -> Tuple[int, int]:
    """Parse rate string like '100/min', '100/minute', '100/1m', '100 per hour'.
    Returns (limit, window_seconds).
    """
    if not isinstance(value, str):
        raise ValueError("Rate must be a string like '100/minute'")

    v = value.strip().lower()
    v = v.replace(" per ", "/").replace(" ", "")
    if "/" not in v:
        raise ValueError("Invalid rate format. Use 'N/period', e.g., '100/minute'")

    left, right = v.split("/", 1)
    if not left.isdigit():
        raise ValueError("Invalid rate limit count")
    limit = int(left)

    # right can be like 'minute', '1m', '60s', '2hours'
    m = re.match(r"^(\d+)?\s*([a-z]+)$", right)
    if m:
        num = m.group(1)
        unit = m.group(2)
        if unit not in _UNITS:
            raise ValueError(f"Unknown time unit: {unit}")
        factor = _UNITS[unit]
        window = (int(num) if num else 1) * factor
        return limit, int(window)

    # also allow plain words like 'minute', 'hour'
    if right in _UNITS:
        return limit, _UNITS[right]

    raise ValueError("Invalid rate period. Examples: '100/min', '100/1h', '100/hour'")


def default_key_func() -> str:
    # Prefer X-API-Key if present, otherwise client IP (respecting X-Forwarded-For)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"api:{api_key}"
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        ip = xff.split(",")[0].strip()
    else:
        ip = request.remote_addr or "unknown"
    return f"ip:{ip}"


# ----------------------------
# Storage backends
# ----------------------------

class Storage:
    def increment(self, key: str, cost: int, window: int) -> Tuple[int, float]:
        """Atomically increment key by cost within window.
        Returns (current_count, reset_ts_epoch_seconds)
        """
        raise NotImplementedError


class InMemoryStorage(Storage):
    def __init__(self):
        self._lock = threading.RLock()
        self._buckets: Dict[str, Tuple[int, float]] = {}

    def increment(self, key: str, cost: int, window: int) -> Tuple[int, float]:
        now = time.time()
        with self._lock:
            count, reset_ts = self._buckets.get(key, (0, now + window))
            if now >= reset_ts:
                count = 0
                reset_ts = now + window
            count += cost
            self._buckets[key] = (count, reset_ts)
            return count, reset_ts


class RedisStorage(Storage):
    def __init__(self, url: str):
        if redis is None:
            raise RuntimeError("redis package is not installed. pip install redis")
        # decode_responses not needed; we use ints
        self._client = redis.Redis.from_url(url)
        self._script = self._client.register_script(
            """
            local current = redis.call('INCRBY', KEYS[1], tonumber(ARGV[1]))
            if current == tonumber(ARGV[1]) then
                redis.call('PEXPIRE', KEYS[1], tonumber(ARGV[2]))
            end
            local ttl = redis.call('PTTL', KEYS[1])
            return {current, ttl}
            """
        )

    def increment(self, key: str, cost: int, window: int) -> Tuple[int, float]:
        res = self._script(keys=[key], args=[int(cost), int(window * 1000)])
        current = int(res[0])
        ttl_ms = int(res[1])
        if ttl_ms < 0:
            # Should not happen due to PEXPIRE, but fallback to full window
            ttl_ms = int(window * 1000)
        reset_ts = time.time() + (ttl_ms / 1000.0)
        return current, reset_ts


# ----------------------------
# Core rate limiter
# ----------------------------

class RateLimiter:
    def __init__(self, storage: Storage):
        self.storage = storage

    def allow(self, key: str, limit: int, window: int, cost: int = 1) -> Dict[str, Any]:
        if cost < 1:
            cost = 1
        count, reset_ts = self.storage.increment(key, cost, window)
        remaining = max(limit - count, 0)
        allowed = count <= limit
        now = time.time()
        reset_in = max(int(round(reset_ts - now)), 0)
        return {
            "key": key,
            "allowed": allowed,
            "limit": int(limit),
            "remaining": int(remaining),
            "reset": int(reset_ts),
            "reset_in": int(reset_in),
            "window": int(window),
            "count": int(count),
        }


# ----------------------------
# Flask integration
# ----------------------------

class RateLimitSpec:
    def __init__(
        self,
        limit_str: str,
        key_func: Optional[Callable[[], str]] = None,
        scope: Optional[str] = None,
        cost: Union[int, Callable[[Any], int]] = 1,
        exempt_when: Optional[Callable[[], bool]] = None,
    ):
        self.limit_str = limit_str
        self.limit, self.window = parse_rate(limit_str)
        self.key_func = key_func
        self.scope = scope or "route"  # 'route', 'global', or 'shared:<name>'
        self.cost = cost
        self.exempt_when = exempt_when


def limit(
    limit_value: str,
    key_func: Optional[Callable[[], str]] = None,
    scope: Optional[str] = None,
    cost: Union[int, Callable[[Any], int]] = 1,
    exempt_when: Optional[Callable[[], bool]] = None,
):
    """Decorator to apply a rate limit to a view.

    - limit_value: e.g., '100/min', '100/1h'.
    - key_func: optional callable returning an identity string (default uses API key or IP).
    - scope: 'route' (default), 'global', or 'shared:<name>' to share limits across routes.
    - cost: integer or callable(request) returning an integer weight for this request.
    - exempt_when: optional callable() returning True to skip limiting for this request.
    """
    spec = RateLimitSpec(limit_value, key_func=key_func, scope=scope, cost=cost, exempt_when=exempt_when)

    def decorator(f):
        setattr(f, "_rate_limit_spec", spec)

        @wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)

        return wrapper

    return decorator


class FlaskRateLimiter:
    def __init__(
        self,
        app=None,
        default_limit: Optional[str] = None,
        storage_uri: Optional[str] = None,
        headers_enabled: bool = True,
        key_func: Callable[[], str] = default_key_func,
        enabled: bool = True,
    ):
        self.app = None
        self.headers_enabled = headers_enabled
        self.key_func = key_func
        self.enabled = enabled

        # Storage selection
        if storage_uri:
            if storage_uri.startswith("redis://") or storage_uri.startswith("rediss://"):
                self.storage: Storage = RedisStorage(storage_uri)
            elif storage_uri.startswith("memory://"):
                self.storage = InMemoryStorage()
            else:
                raise ValueError("Unsupported storage URI. Use redis:// or memory://")
        else:
            self.storage = InMemoryStorage()

        self.rate_limiter = RateLimiter(self.storage)
        self.default_spec: Optional[RateLimitSpec] = RateLimitSpec(default_limit) if default_limit else None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app

        cfg_enabled = app.config.get("RATE_LIMIT_ENABLED", self.enabled)
        self.enabled = bool(cfg_enabled)

        # Configure default limit from app config if not provided
        if self.default_spec is None:
            default_str = app.config.get("RATE_LIMIT_DEFAULT")
            if default_str:
                self.default_spec = RateLimitSpec(default_str)

        # Configure headers
        self.headers_enabled = app.config.get("RATE_LIMIT_HEADERS_ENABLED", self.headers_enabled)

        # Possibly override storage via config
        storage_uri = app.config.get("RATE_LIMIT_STORAGE_URL")
        if storage_uri:
            if storage_uri.startswith("redis://") or storage_uri.startswith("rediss://"):
                self.storage = RedisStorage(storage_uri)
            elif storage_uri.startswith("memory://"):
                self.storage = InMemoryStorage()
            else:
                raise ValueError("Unsupported RATE_LIMIT_STORAGE_URL")
            self.rate_limiter = RateLimiter(self.storage)

        # Key function override
        key_func = app.config.get("RATE_LIMIT_KEY_FUNC")
        if callable(key_func):
            self.key_func = key_func  # type: ignore

        app.before_request(self._before_request)
        app.after_request(self._after_request)

    def _resolve_spec(self) -> Optional[RateLimitSpec]:
        # Identify view-specific spec or fallback to default
        endpoint = request.endpoint
        if not endpoint:
            return self.default_spec
        view = current_app.view_functions.get(endpoint)
        if not view:
            return self.default_spec
        spec: Optional[RateLimitSpec] = getattr(view, "_rate_limit_spec", None)
        if spec:
            return spec
        return self.default_spec

    def _build_key(self, spec: RateLimitSpec, identity: str) -> str:
        scope = (spec.scope or "route").lower()
        if scope == "global":
            return f"rl:global:{identity}"
        if scope.startswith("shared:"):
            name = scope.split(":", 1)[1]
            return f"rl:shared:{name}:{identity}"
        # default per-route scope
        endpoint = request.endpoint or "unknown"
        return f"rl:route:{endpoint}:{identity}"

    def _before_request(self):
        # Skip if disabled or in testing
        if not self.enabled or current_app.config.get("TESTING"):
            return None

        spec = self._resolve_spec()
        if not spec:
            return None

        # Conditional exemption
        if spec.exempt_when:
            try:
                if spec.exempt_when():
                    return None
            except TypeError:
                # Support exempt_when(request)
                if spec.exempt_when(request):  # type: ignore
                    return None

        # Identity
        key_func = spec.key_func or self.key_func
        identity = key_func()
        key = self._build_key(spec, identity)

        # Cost
        cost = spec.cost
        if callable(cost):
            try:
                curr_cost = int(cost(request))  # type: ignore
            except TypeError:
                curr_cost = int(cost())  # type: ignore
        else:
            curr_cost = int(cost)
        if curr_cost < 1:
            curr_cost = 1

        result = self.rate_limiter.allow(key, spec.limit, spec.window, cost=curr_cost)
        g._rate_limit_result = result

        if not result["allowed"]:
            # Too many requests
            retry_after = str(max(result.get("reset_in", 0), 0))
            body = {
                "message": "Too Many Requests",
                "limit": result["limit"],
                "remaining": 0,
                "reset_in": result["reset_in"],
            }
            from flask import jsonify, make_response

            resp = make_response(jsonify(body), 429)
            if self.headers_enabled:
                resp.headers["Retry-After"] = retry_after
                resp.headers["X-RateLimit-Limit"] = str(result["limit"])
                resp.headers["X-RateLimit-Remaining"] = "0"
                resp.headers["X-RateLimit-Reset"] = str(result["reset_in"])
            return resp

        return None

    def _after_request(self, response):
        if not self.enabled or current_app.config.get("TESTING"):
            return response
        result = getattr(g, "_rate_limit_result", None)
        if not result:
            return response
        if self.headers_enabled:
            response.headers["X-RateLimit-Limit"] = str(result["limit"])
            response.headers["X-RateLimit-Remaining"] = str(max(result["remaining"], 0))
            response.headers["X-RateLimit-Reset"] = str(result["reset_in"])  # seconds until reset
        return response

