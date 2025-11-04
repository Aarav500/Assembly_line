import os


def _getenv(name: str, default: str | None = None) -> str:
    return os.getenv(name, default) if os.getenv(name) is not None else (default or "")


# Broker and backend
CELERY_BROKER_URL = _getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = _getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# A separate Redis DB for DLQ bookkeeping (attempt counters, parked messages)
REDIS_URL = _getenv("REDIS_URL", _getenv("CELERY_BROKER_URL", "redis://localhost:6379/2"))

# Queues
DEFAULT_QUEUE = _getenv("DEFAULT_QUEUE", "tasks")
DLQ_QUEUE = _getenv("DLQ_QUEUE", "dlq")

# Worker tuning
WORKER_CONCURRENCY = int(_getenv("WORKER_CONCURRENCY", "2"))
PREFETCH_MULTIPLIER = int(_getenv("PREFETCH_MULTIPLIER", "1"))
VISIBILITY_TIMEOUT = int(_getenv("VISIBILITY_TIMEOUT", "3600"))  # seconds

# Retry defaults for tasks
TASK_DEFAULT_MAX_RETRIES = int(_getenv("TASK_DEFAULT_MAX_RETRIES", "5"))
TASK_RETRY_BACKOFF_MAX = int(_getenv("TASK_RETRY_BACKOFF_MAX", "300"))  # seconds

# DLQ recovery policy
DLQ_MAX_RECOVERY_ATTEMPTS = int(_getenv("DLQ_MAX_RECOVERY_ATTEMPTS", "3"))
DLQ_RECOVERY_BACKOFF_SECONDS = int(_getenv("DLQ_RECOVERY_BACKOFF_SECONDS", "60"))
DLQ_RECOVERY_BACKOFF_FACTOR = float(_getenv("DLQ_RECOVERY_BACKOFF_FACTOR", "2"))
DLQ_RECOVERY_BACKOFF_MAX = int(_getenv("DLQ_RECOVERY_BACKOFF_MAX", "600"))

# Celery configuration dictionary
CELERY_CONFIG = {
    "broker_url": CELERY_BROKER_URL,
    "result_backend": CELERY_RESULT_BACKEND,
    "task_default_queue": DEFAULT_QUEUE,
    "task_queues": None,  # configured in celery_app.py to include DLQ
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "worker_prefetch_multiplier": PREFETCH_MULTIPLIER,
    "task_acks_late": True,  # requeue if worker crashes before ack
    "task_reject_on_worker_lost": True,
    "broker_transport_options": {
        "visibility_timeout": VISIBILITY_TIMEOUT,
    },
    "task_default_rate_limit": None,
    "imports": ("app.tasks",),
}

