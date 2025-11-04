import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(32).hex()
    RATE_LIMIT_REQUESTS = 10
    RATE_LIMIT_WINDOW_SEC = 60
    CACHE_DEFAULT_TIMEOUT = 30