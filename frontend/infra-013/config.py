import os


class Config:
    # Shared secret for HMAC signature validation
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")

    # Signature timestamp tolerance (seconds)
    TIMESTAMP_TOLERANCE_SECONDS = int(os.getenv("TIMESTAMP_TOLERANCE_SECONDS", "300"))

    # Retry configuration
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
    BACKOFF_BASE_SECONDS = float(os.getenv("BACKOFF_BASE_SECONDS", "1.0"))
    BACKOFF_FACTOR = float(os.getenv("BACKOFF_FACTOR", "2.0"))
    BACKOFF_MAX_SECONDS = float(os.getenv("BACKOFF_MAX_SECONDS", "60.0"))
    JITTER_SECONDS = float(os.getenv("JITTER_SECONDS", "0.5"))

    # Idempotency cache TTL
    IDEMPOTENCY_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "3600"))
    IDEMPOTENCY_MAXSIZE = int(os.getenv("IDEMPOTENCY_MAXSIZE", "10000"))

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    REQUEST_LOG_HEADERS = [h.strip() for h in os.getenv(
        "REQUEST_LOG_HEADERS", "X-Request-Id,X-Signature,X-Timestamp"
    ).split(",") if h.strip()]

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5000"))

