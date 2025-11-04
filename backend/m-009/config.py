import os
from dotenv import load_dotenv

load_dotenv()


def _as_bool(val: str, default: bool = False) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    APP_NAME = os.getenv("APP_NAME", "My Flask App")
    OWNER_EMAILS = os.getenv("OWNER_EMAILS", "owner@example.com")

    # Dependency scanning
    REQUIREMENTS_FILE = os.getenv("REQUIREMENTS_FILE", "requirements.txt")

    # SMTP / Email
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_USE_TLS = _as_bool(os.getenv("SMTP_USE_TLS", "true"), True)
    SMTP_USE_SSL = _as_bool(os.getenv("SMTP_USE_SSL", "false"), False)
    MAIL_FROM = os.getenv("MAIL_FROM", f"{APP_NAME} Digest <no-reply@localhost>")

    # Scheduler
    DIGEST_ENABLED = _as_bool(os.getenv("DIGEST_ENABLED", "true"), True)
    # Cron-like controls
    DIGEST_DAY_OF_WEEK = os.getenv("DIGEST_DAY_OF_WEEK", "mon")  # mon,tue,... or *
    DIGEST_HOUR = os.getenv("DIGEST_HOUR", "8")  # 0-23
    DIGEST_MINUTE = os.getenv("DIGEST_MINUTE", "0")  # 0-59

    # If SMTP is not configured, emails are saved to outbox directory
    OUTBOX_DIR = os.getenv("OUTBOX_DIR", "outbox")

    # Timeouts
    PIP_AUDIT_TIMEOUT = int(os.getenv("PIP_AUDIT_TIMEOUT", "180"))
    PIP_OUTDATED_TIMEOUT = int(os.getenv("PIP_OUTDATED_TIMEOUT", "60"))

    # Optional: limit list sizes in email
    MAX_VULN_ITEMS = int(os.getenv("MAX_VULN_ITEMS", "200"))
    MAX_OUTDATED_ITEMS = int(os.getenv("MAX_OUTDATED_ITEMS", "200"))

