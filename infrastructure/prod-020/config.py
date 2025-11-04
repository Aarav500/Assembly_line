import os

# Basic configuration values. Override via environment variables as needed.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Stream names for logging decisions and exposures
DECISION_LOG_STREAM = os.getenv("DECISION_LOG_STREAM", "ff:log:decisions")
EXPOSURE_LOG_STREAM = os.getenv("EXPOSURE_LOG_STREAM", "ff:log:exposures")

# Max length (approximate) for Redis streams (to prevent unbounded growth)
STREAM_MAXLEN = int(os.getenv("STREAM_MAXLEN", "10000"))

# Optional global kill switch (env-level). If set to "1", system will act as killed.
GLOBAL_KILL_SWITCH = os.getenv("GLOBAL_KILL_SWITCH", "0") == "1"

