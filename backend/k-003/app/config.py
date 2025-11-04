from __future__ import annotations
import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///%s" % os.path.abspath("scheduler.db"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEFAULT_TIMEZONE = os.environ.get("DEFAULT_TIMEZONE", "UTC")

    MAINTENANCE_DEFAULT_DURATION_MIN = int(os.environ.get("MAINTENANCE_DEFAULT_DURATION_MIN", 60))
    RETRAIN_INSIDE_MAINTENANCE = os.environ.get("RETRAIN_INSIDE_MAINTENANCE", "false").lower() == "true"

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

