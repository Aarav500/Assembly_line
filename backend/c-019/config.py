import os
from pathlib import Path


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _list(name: str, default: str = ""):
    raw = os.getenv(name, default) or ""
    return [s.strip() for s in raw.split(",") if s.strip()]


class Config:
    # Core
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret-change-me")

    # Storage backend: 's3' or 'local'
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")

    # S3 settings
    S3_BUCKET = os.getenv("S3_BUCKET", "")
    S3_REGION = os.getenv("S3_REGION", os.getenv("AWS_REGION", "us-east-1"))
    S3_UPLOAD_EXPIRATION = _int("S3_UPLOAD_EXPIRATION", 900)  # seconds
    S3_DOWNLOAD_EXPIRATION = _int("S3_DOWNLOAD_EXPIRATION", 900)
    S3_DEFAULT_ACL = os.getenv("S3_DEFAULT_ACL", "private")

    # Local storage settings
    LOCAL_STORAGE_PATH = Path(os.getenv("LOCAL_STORAGE_PATH", "./uploads")).resolve()
    LOCAL_UPLOAD_EXPIRATION = _int("LOCAL_UPLOAD_EXPIRATION", 900)
    LOCAL_DOWNLOAD_EXPIRATION = _int("LOCAL_DOWNLOAD_EXPIRATION", 900)

    # Validation
    MAX_FILE_SIZE_BYTES = _int("MAX_FILE_SIZE_BYTES", 10 * 1024 * 1024)  # 10MB
    ALLOWED_MIME_PREFIXES = _list("ALLOWED_MIME_PREFIXES", "image/,application/pdf")

