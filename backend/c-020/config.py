import os

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DEFAULT_TTL = int(os.environ.get("DEFAULT_TTL", "300"))
PURGE_TOKEN = os.environ.get("PURGE_TOKEN", "devtoken")
VARNISH_HOST = os.environ.get("VARNISH_HOST", "localhost")
VARNISH_PORT = int(os.environ.get("VARNISH_PORT", "6081"))
CACHE_NAMESPACE = os.environ.get("CACHE_NAMESPACE", "demo")

