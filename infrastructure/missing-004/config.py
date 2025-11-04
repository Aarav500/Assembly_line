import os
from dataclasses import dataclass


def env_bool(name: str, default: bool = False):
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///emails.db")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "sendgrid")  # or "ses"

    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "no-reply@example.com")
    FROM_NAME: str = os.getenv("FROM_NAME", "Example App")

    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")

    SES_REGION: str = os.getenv("SES_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")

    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "5"))
    RETRY_BACKOFF_BASE: int = int(os.getenv("RETRY_BACKOFF_BASE", "5"))  # seconds
    RETRY_BACKOFF_FACTOR: int = int(os.getenv("RETRY_BACKOFF_FACTOR", "2"))

    TEMPLATE_FOLDER: str = os.getenv("TEMPLATE_FOLDER", "templates/email")


settings = Settings()
