import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    CELERY_TIMEZONE: str = os.getenv("CELERY_TIMEZONE", "UTC")
    CELERY_TASK_DEFAULT_QUEUE: str = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "default")
    CELERY_WORKER_QUEUES: str = os.getenv("CELERY_WORKER_QUEUES", "default,high,low")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()

