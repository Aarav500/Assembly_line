import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

    # Scheduler/maintenance
    SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "1") not in ("0", "false", "False")
    MAINTENANCE_INTERVAL_SECONDS = int(os.environ.get("MAINTENANCE_INTERVAL_SECONDS", "60"))

    # Purge behavior defaults
    DEFAULT_PURGE_HARD = os.environ.get("DEFAULT_PURGE_HARD", "0") in ("1", "true", "True")

