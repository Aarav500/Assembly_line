import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///kb_diff.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Scheduler
    ENABLE_SCHEDULER = os.environ.get("ENABLE_SCHEDULER", "1") == "1"
    SCHEDULER_INTERVAL_SECONDS = int(os.environ.get("SCHEDULER_INTERVAL_SECONDS", "60"))

    # Notifications
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "1") == "1"
    MAIL_FROM = os.environ.get("MAIL_FROM", "kb-diff@localhost")

    DEFAULT_NOTIFY_EMAIL = os.environ.get("DEFAULT_NOTIFY_EMAIL", "")
    DEFAULT_NOTIFY_WEBHOOK = os.environ.get("DEFAULT_NOTIFY_WEBHOOK", "")

    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000")

