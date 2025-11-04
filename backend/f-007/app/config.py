import os


class Config:
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")

    # Handoff worker
    HANDOFF_WORKER_ENABLED = os.getenv("HANDOFF_WORKER_ENABLED", "true").lower() == "true"
    HANDOFF_WORKER_INTERVAL = int(os.getenv("HANDOFF_WORKER_INTERVAL", "30"))  # seconds

    # Slack
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    SLACK_DEFAULT_CHANNEL = os.getenv("SLACK_DEFAULT_CHANNEL", "#oncall-alerts")

    # SMTP
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "oncall-bot@example.com")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # General
    DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "UTC")

