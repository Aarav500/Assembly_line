import os
from datetime import timedelta


def str_to_bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


class Config:
    # Flask
    DEBUG = str_to_bool(os.getenv("DEBUG"), False)
    SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24).hex())

    # S3/MinIO
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
    S3_REGION = os.getenv("S3_REGION", "us-east-1")
    S3_BUCKET = os.getenv("S3_BUCKET", "files")
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")  # Use for MinIO or custom endpoint
    S3_FORCE_PATH_STYLE = str_to_bool(os.getenv("S3_FORCE_PATH_STYLE"), True)  # True recommended for MinIO
    S3_SIGNATURE_VERSION = os.getenv("S3_SIGNATURE_VERSION", "s3v4")

    # CDN
    CDN_BASE_URL = os.getenv("CDN_BASE_URL")  # e.g., https://cdn.example.com

    # Access control
    API_TOKENS = [t.strip() for t in os.getenv("API_TOKENS", "").split(",") if t.strip()]  # comma-separated

    # Defaults
    DEFAULT_ACL_PUBLIC = str_to_bool(os.getenv("DEFAULT_ACL_PUBLIC"), False)
    DEFAULT_PREFIX = os.getenv("DEFAULT_PREFIX", "uploads/")
    PRESIGN_EXPIRES = int(os.getenv("PRESIGN_EXPIRES", "900"))  # seconds
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(50 * 1024 * 1024)))  # 50MB

    # Thumbnails
    THUMBNAIL_SIZES = [int(s) for s in os.getenv("THUMBNAIL_SIZES", "256,512").split(",") if s.strip()]


config = Config()

