import os

def _getenv_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _getenv_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _getenv_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres",
)
DB_POOL_SIZE = _getenv_int("DB_POOL_SIZE", 5)
DB_MAX_OVERFLOW = _getenv_int("DB_MAX_OVERFLOW", 10)
DB_POOL_RECYCLE = _getenv_int("DB_POOL_RECYCLE", 1800)  # seconds
DB_POOL_TIMEOUT = _getenv_int("DB_POOL_TIMEOUT", 30)  # seconds
DB_CONNECT_TIMEOUT = _getenv_int("DB_CONNECT_TIMEOUT", 5)  # seconds, libpq connect_timeout
DB_ECHO = _getenv_bool("DB_ECHO", False)

# Retry
RETRY_MAX_ATTEMPTS = _getenv_int("RETRY_MAX_ATTEMPTS", 5)
RETRY_BASE_DELAY = _getenv_float("RETRY_BASE_DELAY", 0.2)
RETRY_MAX_DELAY = _getenv_float("RETRY_MAX_DELAY", 3.0)

# Circuit Breaker
CIRCUIT_FAILURE_THRESHOLD = _getenv_int("CIRCUIT_FAILURE_THRESHOLD", 5)
CIRCUIT_RECOVERY_TIMEOUT = _getenv_int("CIRCUIT_RECOVERY_TIMEOUT", 30)  # seconds
CIRCUIT_HALF_OPEN_MAX_SUCCESS = _getenv_int("CIRCUIT_HALF_OPEN_MAX_SUCCESS", 2)

# Healthcheck
HEALTHCHECK_INTERVAL = _getenv_int("HEALTHCHECK_INTERVAL", 10)  # seconds
HEALTHCHECK_LOG_ERRORS = _getenv_bool("HEALTHCHECK_LOG_ERRORS", True)

