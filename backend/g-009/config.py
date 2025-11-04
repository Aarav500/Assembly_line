import os

class Config:
    # Networking
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    # Cache settings
    REDIS_URL = os.getenv("REDIS_URL")
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400"))  # 1 day default

    # In-flight de-duplication
    INFLIGHT_TTL_SECONDS = int(os.getenv("INFLIGHT_TTL_SECONDS", "60"))
    INFLIGHT_WAIT_TIMEOUT_SECONDS = int(os.getenv("INFLIGHT_WAIT_TIMEOUT_SECONDS", "30"))
    INFLIGHT_POLL_INTERVAL_SECONDS = float(os.getenv("INFLIGHT_POLL_INTERVAL_SECONDS", "0.2"))

    # Request size limit (1 MiB)
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "1048576"))

