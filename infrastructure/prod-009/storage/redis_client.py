import os
import redis
from config import Config

_config = Config()

_redis_client = None

def get_redis():
    global _redis_client
    if _redis_client is None:
        if _config.REDIS_URL:
            _redis_client = redis.Redis.from_url(_config.REDIS_URL, decode_responses=True)
        else:
            _redis_client = redis.Redis(host=_config.REDIS_HOST, port=_config.REDIS_PORT, db=_config.REDIS_DB, decode_responses=True)
    return _redis_client

