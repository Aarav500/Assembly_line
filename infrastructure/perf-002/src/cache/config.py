import os

def get_env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).lower() in ("1", "true", "yes", "on")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_NAMESPACE = os.getenv("CACHE_NAMESPACE", "app")
CACHE_DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL", "300"))
CACHE_REFRESH_AHEAD_SECONDS = int(os.getenv("CACHE_REFRESH_AHEAD_SECONDS", "30"))
CACHE_MONITOR_PORT = int(os.getenv("CACHE_MONITOR_PORT", "8081"))
CACHE_WARMER_INTERVAL = int(os.getenv("CACHE_WARMER_INTERVAL", "60"))
CACHE_WARMER_TOPN = int(os.getenv("CACHE_WARMER_TOPN", "100"))
CACHE_ENABLE_PUBSUB = get_env_bool("CACHE_ENABLE_PUBSUB", True)
CACHE_LOCK_TIMEOUT = int(os.getenv("CACHE_LOCK_TIMEOUT", "10"))
CACHE_LOCK_WAIT_TIMEOUT = int(os.getenv("CACHE_LOCK_WAIT_TIMEOUT", "5"))

