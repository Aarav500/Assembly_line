import os


class Config:
    # Flask
    ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    PORT = int(os.getenv("PORT", "5000"))

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app.db")
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "5"))
    DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))  # seconds

    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))

    # External HTTP client
    HTTP_POOL_CONNECTIONS = int(os.getenv("HTTP_POOL_CONNECTIONS", "10"))
    HTTP_POOL_MAXSIZE = int(os.getenv("HTTP_POOL_MAXSIZE", "50"))
    HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "2"))
    HTTP_CONCURRENCY_LIMIT = int(os.getenv("HTTP_CONCURRENCY_LIMIT", "20"))
    HTTP_RATE_LIMIT_PER_SEC = float(os.getenv("HTTP_RATE_LIMIT_PER_SEC", "20"))
    HTTP_RATE_LIMIT_BURST = float(os.getenv("HTTP_RATE_LIMIT_BURST", "40"))
    HTTP_DEFAULT_TIMEOUT = float(os.getenv("HTTP_DEFAULT_TIMEOUT", "10"))

    # Monitoring
    METRICS_ENABLED = os.getenv("METRICS_ENABLED", "1") == "1"
    METRICS_ROUTE = os.getenv("METRICS_ROUTE", "/metrics")

    # Health check
    HEALTHCHECK_EXTERNAL_URL = os.getenv("HEALTHCHECK_EXTERNAL_URL", "https://httpbin.org/status/204")

