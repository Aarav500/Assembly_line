import asyncio
import os
import random
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from redis_service import (
    RedisConfig,
    init_redis,
    close_redis,
    CacheService,
    SessionStore,
    RateLimiter,
    RateLimitAlgorithm,
    PubSubService,
)


async def demo_cache(cache: CacheService):
    print("=== Cache Demo ===")
    key = cache.key("user", "42")
    await cache.set(key, {"name": "Alice", "age": 30}, ttl_seconds=10)
    val = await cache.get(key)
    print("cached:", val)

    async def compute():
        await asyncio.sleep(0.2)
        return {"name": "Alice", "age": 31}

    val2 = await cache.get_or_set(cache.key("profile", "42"), compute, ttl_seconds=10)
    print("get_or_set:", val2)


async def demo_session(sessions: SessionStore):
    print("=== Session Demo ===")
    sid = await sessions.create_session("user_123", {"role": "admin"}, ttl_seconds=5)
    print("created session:", sid)
    s = await sessions.get_session(sid)
    print("session data:", s)
    await sessions.update_session(sid, {"role": "editor"})
    print("updated:", await sessions.get_session(sid))
    await sessions.renew_session(sid, ttl_seconds=10)
    print("renewed ttl (seconds):", await sessions.redis.ttl(sessions.key(sid)))
    await sessions.destroy_session(sid)
    print("destroyed session. exists?", await sessions.get_session(sid))


async def demo_rate_limit(rl_fixed: RateLimiter, rl_sliding: RateLimiter):
    print("=== Rate Limiter Demo ===")
    bucket = "login:127.0.0.1"
    print("Fixed window: 5 req / 2 sec")
    for i in range(7):
        r = await rl_fixed.allow(bucket, limit=5, window_ms=2000)
        print(f"fixed attempt {i+1}: allowed={r.allowed} remaining={r.remaining} retry_after_ms={r.retry_after_ms}")
        await asyncio.sleep(0.2)
    await asyncio.sleep(2.2)
    r = await rl_fixed.allow(bucket, limit=5, window_ms=2000)
    print("after reset, allowed:", r.allowed)

    print("Sliding window: 3 req / 1 sec")
    bucket2 = "search:user_42"
    for i in range(5):
        r = await rl_sliding.allow(bucket2, limit=3, window_ms=1000)
        print(f"sliding attempt {i+1}: allowed={r.allowed} remaining={r.remaining} retry_after_ms={r.retry_after_ms}")
        await asyncio.sleep(0.25)


async def demo_pubsub(ps: PubSubService):
    print("=== Pub/Sub Demo ===")
    channel = ps.channel("events")

    async def subscriber():
        async for msg in ps.subscribe(channel):
            print("received:", msg)
            break

    task = asyncio.create_task(subscriber())
    await asyncio.sleep(0.1)
    await ps.publish(channel, {"event": "user.signup", "user_id": 42})
    await asyncio.wait_for(task, timeout=5)


async def main():
    config = RedisConfig.from_env()
    redis = await init_redis(config)

    cache = CacheService(redis, config)
    sessions = SessionStore(redis, config)
    rl_fixed = RateLimiter(redis, config, algorithm=RateLimitAlgorithm.FIXED_WINDOW)
    rl_sliding = RateLimiter(redis, config, algorithm=RateLimitAlgorithm.SLIDING_WINDOW)
    ps = PubSubService(redis, config)

    await demo_cache(cache)
    await demo_session(sessions)
    await demo_rate_limit(rl_fixed, rl_sliding)
    await demo_pubsub(ps)

    await close_redis()


if __name__ == "__main__":
    asyncio.run(main())

