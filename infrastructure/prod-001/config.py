import os

class Config:
    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    RL_REDIS_KEY_PREFIX = os.getenv("RL_REDIS_KEY_PREFIX", "rl")

    # Core rate limit
    RL_REQUEST_LIMIT = int(os.getenv("RL_REQUEST_LIMIT", "100"))  # requests
    RL_WINDOW_SECONDS = int(os.getenv("RL_WINDOW_SECONDS", "60"))  # seconds

    # Ban logic
    RL_BAN_THRESHOLD = int(os.getenv("RL_BAN_THRESHOLD", "5"))  # violations within monitor window
    RL_BAN_MONITOR_WINDOW = int(os.getenv("RL_BAN_MONITOR_WINDOW", "300"))  # seconds
    RL_BAN_DURATION = int(os.getenv("RL_BAN_DURATION", "900"))  # seconds

    # Networking / IP handling
    RL_TRUST_PROXY_HEADERS = os.getenv("RL_TRUST_PROXY_HEADERS", "true").lower() in ("1","true","yes","on")
    RL_REAL_IP_HEADER = os.getenv("RL_REAL_IP_HEADER", "X-Forwarded-For")
    RL_TRUSTED_PROXIES = [p.strip() for p in os.getenv("RL_TRUSTED_PROXIES", "").split(",") if p.strip()]

    # Whitelisting (IPs or CIDRs)
    RL_IP_WHITELIST = [w.strip() for w in os.getenv("RL_IP_WHITELIST", "").split(",") if w.strip()]

    # Paths and methods to skip rate limiting
    RL_SKIP_PATHS = [p.strip() for p in os.getenv("RL_SKIP_PATHS", "/health").split(",") if p.strip()]
    RL_SKIP_METHODS = [m.strip().upper() for m in os.getenv("RL_SKIP_METHODS", "OPTIONS,HEAD").split(",") if m.strip()]

    # Whether to include rate limit headers in responses
    RL_ADD_HEADERS = os.getenv("RL_ADD_HEADERS", "true").lower() in ("1","true","yes","on")

    # Enable debug logging for middleware
    RL_DEBUG = os.getenv("RL_DEBUG", "false").lower() in ("1","true","yes","on")

