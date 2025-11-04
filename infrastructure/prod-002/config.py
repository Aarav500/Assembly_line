import os
from dataclasses import dataclass, field
from typing import List


def getenv_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def getenv_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def getenv_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


@dataclass
class Config:
    APP_NAME: str = os.getenv("APP_NAME", "comprehensive-error-handling-logging-framework")
    ENV: str = os.getenv("FLASK_ENV", os.getenv("ENV", "production"))
    DEBUG: bool = getenv_bool("DEBUG", False)
    TESTING: bool = getenv_bool("TESTING", False)
    PORT: int = getenv_int("PORT", 8000)

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_JSON: bool = getenv_bool("LOG_JSON", True)
    LOG_REDACT_FIELDS: List[str] = field(default_factory=lambda: (
        os.getenv("LOG_REDACT_FIELDS", "authorization,proxy-authorization,x-api-key,x-auth-token,api_key,token,password,secret,set-cookie,cookie")
        .replace(" ", "")
        .split(",")
    ))

    # Stack trace sanitization limits
    MAX_STACK_FRAMES: int = getenv_int("MAX_STACK_FRAMES", 20)

    # Sentry
    SENTRY_DSN: str | None = os.getenv("SENTRY_DSN")
    SENTRY_ENABLED: bool = getenv_bool("SENTRY_ENABLED", False)
    SENTRY_ENVIRONMENT: str = os.getenv("SENTRY_ENVIRONMENT", ENV)
    SENTRY_RELEASE: str | None = os.getenv("SENTRY_RELEASE")
    SENTRY_TRACES_SAMPLE_RATE: float = getenv_float("SENTRY_TRACES_SAMPLE_RATE", 0.0)

    # Recovery / Circuit Breaker
    CB_FAILURE_THRESHOLD: int = getenv_int("CB_FAILURE_THRESHOLD", 5)
    CB_RECOVERY_TIMEOUT: float = getenv_float("CB_RECOVERY_TIMEOUT", 30.0)

    # Retry defaults
    RETRY_DEFAULTS_RETRIES: int = getenv_int("RETRY_DEFAULTS_RETRIES", 2)
    RETRY_DEFAULTS_BACKOFF: float = getenv_float("RETRY_DEFAULTS_BACKOFF", 0.2)
    RETRY_DEFAULTS_JITTER: float = getenv_float("RETRY_DEFAULTS_JITTER", 0.1)

