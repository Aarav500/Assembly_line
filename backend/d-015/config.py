import os
import pytz

class Config:
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", "5000"))

    TZ_NAME = os.getenv("TZ", "UTC")
    TIMEZONE = pytz.timezone(TZ_NAME)

    # Cron schedules in standard 5-field format: minute hour day month dow
    INTEGRATION_CRON = os.getenv("INTEGRATION_CRON", "0 2 * * *")
    LOADTEST_CRON = os.getenv("LOADTEST_CRON", "0 3 * * *")

    REPORTS_DIR = os.getenv("REPORTS_DIR", "reports")

    # Base URL for tests (integration tests and load tests)
    DEFAULT_BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
    BASE_URL = DEFAULT_BASE_URL
    LOADTEST_URL = os.getenv("LOADTEST_URL", f"{BASE_URL}/compute?x=5000")

    # Load test parameters
    LOADTEST_DURATION = int(os.getenv("LOADTEST_DURATION", "60"))  # seconds
    LOADTEST_CONCURRENCY = int(os.getenv("LOADTEST_CONCURRENCY", "10"))
    LOADTEST_RPS = float(os.getenv("LOADTEST_RPS", "50"))
    LOADTEST_TIMEOUT = float(os.getenv("LOADTEST_TIMEOUT", "5.0"))

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

