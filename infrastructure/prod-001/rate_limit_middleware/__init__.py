import time
import logging
import ipaddress
from typing import List, Optional
from flask import request, current_app, g

# Lua script implementing sliding window using a sorted set per IP
# Returns: {allowedFlag (1/0), count, oldestScore}
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local seq_key = key .. ':seq'
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local expire = math.ceil(window / 1000)
local member = tostring(now) .. '-' .. tostring(redis.call('INCRBY', seq_key, 1))
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, expire)
redis.call('EXPIRE', seq_key, expire)
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
local oldestScore = now
if oldest and #oldest >= 2 then
  oldestScore = tonumber(oldest[2])
end
if count <= limit then
  return {1, count, oldestScore}
else
  return {0, count, oldestScore}
end
"""

class RateLimitMiddleware:
    def __init__(self, app=None, redis_client=None, **kwargs):
        self.app = None
        self.r = redis_client
        self.key_prefix = None
        self.logger = logging.getLogger("rate_limit")
        self.whitelist_networks: List[ipaddress._BaseNetwork] = []
        if app is not None:
            self.init_app(app, redis_client, **kwargs)

    def init_app(self, app, redis_client=None, **kwargs):
        self.app = app
        self.r = redis_client or self._create_redis_client()
        self.key_prefix = app.config.get("RL_REDIS_KEY_PREFIX", "rl")
        self._compile_whitelist(app.config.get("RL_IP_WHITELIST", []))
        if app.config.get("RL_DEBUG"):
            logging.basicConfig(level=logging.DEBUG)
        app.before_request(self._before_request)
        app.after_request(self._after_request)

    def _create_redis_client(self):
        from redis import Redis
        url = current_app.config.get("REDIS_URL") if current_app else None
        # Fallback in case current_app not available at import
        if url is None and self.app is not None:
            url = self.app.config.get("REDIS_URL")
        return Redis.from_url(url, decode_responses=False)

    def _compile_whitelist(self, entries: List[str]):
        nets = []
        for e in entries:
            try:
                if "/" in e:
                    nets.append(ipaddress.ip_network(e, strict=False))
                else:
                    # Single IP -> convert to /32 or /128 network
                    ip = ipaddress.ip_address(e)
                    nets.append(ipaddress.ip_network(ip.exploded + ("/32" if ip.version == 4 else "/128"), strict=False))
            except ValueError:
                continue
        self.whitelist_networks = nets

    def _client_ip(self) -> str:
        app = self.app or current_app
        trust_proxy = app.config.get("RL_TRUST_PROXY_HEADERS", True)
        hdr = app.config.get("RL_REAL_IP_HEADER", "X-Forwarded-For")
        remote = request.remote_addr or "0.0.0.0"
        if trust_proxy and hdr in request.headers:
            # Take first non-empty IP from X-Forwarded-For
            candidates = [x.strip() for x in request.headers.get(hdr, "").split(",") if x.strip()]
            if candidates:
                return candidates[0]
        return remote

    def _is_whitelisted(self, ip: str) -> bool:
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            return False
        for net in self.whitelist_networks:
            if ip_obj in net:
                return True
        return False

    def _ban_key(self, ip: str) -> str:
        return f"{self.key_prefix}:ban:{ip}"

    def _bucket_key(self, ip: str) -> str:
        return f"{self.key_prefix}:z:{ip}"

    def _viol_key(self, ip: str) -> str:
        return f"{self.key_prefix}:viol:{ip}"

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _get_limits_for_request(self):
        app = self.app or current_app
        limit = app.config.get("RL_REQUEST_LIMIT", 100)
        window_s = app.config.get("RL_WINDOW_SECONDS", 60)
        return int(limit), int(window_s)

    def _should_skip(self) -> bool:
        app = self.app or current_app
        # Skip methods
        if request.method.upper() in set(app.config.get("RL_SKIP_METHODS", [])):
            return True
        # Skip paths
        path = request.path
        for p in app.config.get("RL_SKIP_PATHS", []):
            if p and path.startswith(p):
                return True
        return False

    def _is_banned(self, ip: str) -> Optional[int]:
        # Returns remaining ban ttl in seconds if banned, else None
        ttl = self.r.ttl(self._ban_key(ip))
        if ttl and ttl > 0:
            return int(ttl)
        # For Redis 6, TTL may return -2 (no key) or -1 (no expire)
        if ttl == -1:
            return 1  # treat as banned with unknown ttl
        return None

    def _register_violation_and_maybe_ban(self, ip: str):
        app = self.app or current_app
        viol_key = self._viol_key(ip)
        ban_key = self._ban_key(ip)
        ban_threshold = int(app.config.get("RL_BAN_THRESHOLD", 5))
        ban_monitor = int(app.config.get("RL_BAN_MONITOR_WINDOW", 300))
        ban_duration = int(app.config.get("RL_BAN_DURATION", 900))
        pipe = self.r.pipeline()
        pipe.incr(viol_key)
        pipe.expire(viol_key, ban_monitor)
        viol_count, _ = pipe.execute()
        if viol_count >= ban_threshold:
            # Ban and reset violations window
            self.r.setex(ban_key, ban_duration, b"1")
            # Optionally clear violations counter
            self.r.delete(viol_key)
            return True, ban_duration
        return False, None

    def _before_request(self):
        app = self.app or current_app
        if self._should_skip():
            g.rate_limit = None
            return None
        ip = self._client_ip()
        if self._is_whitelisted(ip):
            g.rate_limit = {
                "ip": ip,
                "limit": None,
                "remaining": None,
                "reset": None,
                "whitelisted": True,
            }
            return None
        ban_ttl = self._is_banned(ip)
        if ban_ttl:
            return self._reject_banned(ip, ban_ttl)
        limit, window_s = self._get_limits_for_request()
        window_ms = int(window_s * 1000)
        key = self._bucket_key(ip)
        now_ms = self._now_ms()
        try:
            res = self.r.eval(SLIDING_WINDOW_LUA, 1, key, now_ms, window_ms, int(limit))
            # redis returns list of integers (bytes in older) -> handle generically
            allowed = int(res[0]) == 1
            count = int(res[1])
            oldest_ms = int(res[2]) if len(res) > 2 else now_ms
        except Exception as e:
            # Fail-open on Redis errors
            if app.config.get("RL_DEBUG"):
                self.logger.exception("Rate limit Redis error: %s", e)
            g.rate_limit = None
            return None

        remaining = max(0, int(limit) - count)
        reset_s = max(0, int((window_ms - max(0, now_ms - oldest_ms)) / 1000))

        g.rate_limit = {
            "ip": ip,
            "limit": int(limit),
            "remaining": remaining,
            "reset": reset_s,
            "whitelisted": False,
        }

        if allowed:
            return None

        banned_now, ban_dur = self._register_violation_and_maybe_ban(ip)
        if banned_now:
            return self._reject_banned(ip, ban_dur)
        return self._reject_rate_limited(ip, reset_s)

    def _after_request(self, response):
        app = self.app or current_app
        if app.config.get("RL_ADD_HEADERS", True) and hasattr(g, "rate_limit") and g.rate_limit is not None:
            rl = g.rate_limit
            if not rl.get("whitelisted") and rl.get("limit") is not None:
                response.headers["X-RateLimit-Limit"] = str(rl.get("limit"))
                response.headers["X-RateLimit-Remaining"] = str(max(0, rl.get("remaining", 0)))
                response.headers["X-RateLimit-Reset"] = str(rl.get("reset", 0))
        return response

    def _reject_banned(self, ip: str, ban_ttl: Optional[int]):
        from flask import jsonify
        retry_after = int(ban_ttl) if ban_ttl is not None else 0
        resp = jsonify({
            "error": "forbidden",
            "reason": "ip_banned",
            "ip": ip,
            "retry_after": retry_after,
        })
        resp.status_code = 403
        if retry_after > 0:
            resp.headers["Retry-After"] = str(retry_after)
        return resp

    def _reject_rate_limited(self, ip: str, reset_s: int):
        from flask import jsonify
        resp = jsonify({
            "error": "rate_limited",
            "ip": ip,
            "retry_after": int(reset_s),
        })
        resp.status_code = 429
        resp.headers["Retry-After"] = str(int(reset_s))
        return resp

__all__ = ["RateLimitMiddleware"]

