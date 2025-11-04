import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///data/app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", "data/snapshots")
    RESTORE_DIR = os.getenv("RESTORE_DIR", "data/restores")

    SCHEDULER_JOB_DEFAULTS = {
        "misfire_grace_time": int(os.getenv("MISFIRE_GRACE", "300")),
        "coalesce": True,
        "max_instances": 1,
    }
    TIMEZONE = os.getenv("TIMEZONE", "UTC")

