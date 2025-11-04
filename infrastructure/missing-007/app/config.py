import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
    MESSAGE_QUEUE_URL = os.getenv("MESSAGE_QUEUE_URL", REDIS_URL)
    CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "*")
    SOCKETIO_LOGGER = os.getenv("SOCKETIO_LOGGER", "true").lower() == "true"
    SOCKETIO_ENGINEIO_LOGGER = os.getenv("SOCKETIO_ENGINEIO_LOGGER", "false").lower() == "true"

