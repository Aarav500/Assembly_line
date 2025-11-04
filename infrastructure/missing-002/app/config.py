import os
from datetime import timedelta


def _bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24))
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mail
    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "1025"))
    MAIL_USE_TLS = _bool(os.getenv("MAIL_USE_TLS"), False)
    MAIL_USE_SSL = _bool(os.getenv("MAIL_USE_SSL"), False)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "No Reply <no-reply@example.com>")
    MAIL_SUPPRESS_SEND = _bool(os.getenv("MAIL_SUPPRESS_SEND"), False)

    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    SECURITY_EMAIL_TOKEN_HOURS = int(os.getenv("SECURITY_EMAIL_TOKEN_HOURS", "48"))
    SECURITY_RESET_TOKEN_HOURS = int(os.getenv("SECURITY_RESET_TOKEN_HOURS", "2"))
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")

