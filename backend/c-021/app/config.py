import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")

    # Redis / Brokers
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

    # Celery
    TASK_DEFAULT_QUEUE = os.getenv("TASK_DEFAULT_QUEUE", "default")
    CELERY_TASK_DEFAULT_QUEUE = TASK_DEFAULT_QUEUE
    CELERY_TASK_ALWAYS_EAGER = os.getenv("TASK_ALWAYS_EAGER", "false").lower() == "true"
    CELERY_TIMEZONE = os.getenv("CELERY_TIMEZONE", "UTC")

    # RQ
    RQ_REDIS_URL = os.getenv("RQ_REDIS_URL", REDIS_URL)

    # API
    API_PREFIX = os.getenv("API_PREFIX", "/api")

