import time
from storage.redis_client import get_redis

# Lua script to atomically increment a key with TTL and enforce a limit
# Returns: {allowed_flag, current_count, limit, ttl}
RATE_LIMIT_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local now = redis.call('INCR', key)
if now == 1 then
  redis.call('EXPIRE', key, ttl)
end
if now > limit then
  local ttl_left = redis.call('TTL', key)
  return {0, now, limit, ttl_left}
else
  local ttl_left = redis.call('TTL', key)
  return {1, now, limit, ttl_left}
end
"""

_script_sha = None


def _get_script_sha():
    global _script_sha
    r = get_redis()
    if not _script_sha:
        _script_sha = r.script_load(RATE_LIMIT_LUA)
    return _script_sha


def _eval_rate_limit(key: str, limit: int, ttl_seconds: int):
    r = get_redis()
    sha = _get_script_sha()
    try:
        res = r.evalsha(sha, 1, key, limit, ttl_seconds)
    except Exception:
        # Fallback if script cache flushed
        res = r.eval(RATE_LIMIT_LUA, 1, key, limit, ttl_seconds)
    allowed = int(res[0]) == 1
    current = int(res[1])
    lim = int(res[2])
    ttl = int(res[3])
    return allowed, current, lim, ttl


def current_epoch():
    return int(time.time())


def epoch_minute():
    return int(time.time() // 60)


def build_keys(user_id: str):
    sec = current_epoch()
    minute = epoch_minute()
    return {
        "sec": f"rl:{user_id}:s:{sec}",
        "min": f"rl:{user_id}:m:{minute}",
    }


def check_and_increment(user_id: str, rps: int | None = None, rpm: int | None = None):
    keys = build_keys(user_id)
    headers = {}
    # Default allowed
    allowed = True
    reasons = []

    if rps and rps > 0:
        ok, cur, limit, ttl = _eval_rate_limit(keys["sec"], rps, 2)
        headers["X-RateLimit-Limit-Second"] = str(limit)
        headers["X-RateLimit-Remaining-Second"] = str(max(0, limit - cur))
        headers["X-RateLimit-Reset-Second"] = str(int(time.time()) + ttl)
        if not ok:
            allowed = False
            reasons.append("per-second limit exceeded")

    if rpm and rpm > 0:
        ok, cur, limit, ttl = _eval_rate_limit(keys["min"], rpm, 70)
        headers["X-RateLimit-Limit-Minute"] = str(limit)
        headers["X-RateLimit-Remaining-Minute"] = str(max(0, limit - cur))
        headers["X-RateLimit-Reset-Minute"] = str((int(time.time() // 60) * 60) + ttl)
        if not ok:
            allowed = False
            reasons.append("per-minute limit exceeded")

    return allowed, headers, ", ".join(reasons)

