import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///notification_prefs.db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "UTC")
    # For demonstration of digest batching window
    DIGEST_LOOKBACK_HOURS = int(os.getenv("DIGEST_LOOKBACK_HOURS", "168"))  # 7 days
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

