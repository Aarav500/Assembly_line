import os
from dataclasses import dataclass


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


@dataclass
class Settings:
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Queue
    queue_key: str = os.getenv("QUEUE_KEY", "webhook:queue")

    # Defaults for backoff and attempts
    default_max_attempts: int = _get_int("DEFAULT_MAX_ATTEMPTS", 5)
    backoff_base: float = _get_float("BACKOFF_BASE", 1.0)  # seconds
    backoff_factor: float = _get_float("BACKOFF_FACTOR", 2.0)
    backoff_jitter: float = _get_float("BACKOFF_JITTER", 0.25)  # seconds
    backoff_max: float = _get_float("MAX_BACKOFF", 300.0)

    request_timeout: float = _get_float("REQUEST_TIMEOUT", 10.0)
    user_agent: str = os.getenv("USER_AGENT", "WebhookDelivery/1.0")

    # Retention
    job_retention_seconds: int = _get_int("JOB_RETENTION_SECONDS", 86400)  # 1 day
    status_retention_seconds: int = _get_int("STATUS_RETENTION_SECONDS", 604800)  # 7 days

    # Worker
    poll_interval: float = _get_float("POLL_INTERVAL", 0.5)

    # Failure notifications
    failure_notify_url: str | None = os.getenv("FAILURE_NOTIFY_URL", None)


settings = Settings()

