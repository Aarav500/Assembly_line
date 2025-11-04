import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REPORTS_DIR = os.environ.get("REPORTS_DIR", os.path.join(os.path.dirname(__file__), "reports"))
    SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "1") not in ("0", "false", "False")
    TIMEZONE = os.environ.get("TIMEZONE", "UTC")

