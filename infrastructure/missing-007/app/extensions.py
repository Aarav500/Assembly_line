import redis
from flask_socketio import SocketIO
from .config import Config

socketio = SocketIO()
redis_client = redis.Redis.from_url(Config.REDIS_URL, decode_responses=True)

