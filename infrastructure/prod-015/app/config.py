import os

class Config:
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    # Database
    DB_USER = os.getenv("POSTGRES_USER", "postgres")
    DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "auditdb")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Audit
    AUDIT_HMAC_SECRET = os.getenv("AUDIT_HMAC_SECRET", "change-this-hmac-secret")
    AUDIT_MAX_BODY = int(os.getenv("AUDIT_MAX_BODY", "4096"))
    AUDIT_REDACT_KEYS = set(
        k.lower()
        for k in (os.getenv("AUDIT_REDACT_KEYS", "password,token,authorization,api_key,apikey,secret").split(","))
        if k
    )
    AUDIT_CAPTURE_HEADERS = set(
        h.strip()
        for h in os.getenv(
            "AUDIT_CAPTURE_HEADERS",
            "User-Agent,Content-Type,Content-Length,Authorization,X-Request-Id",
        ).split(",")
        if h
    )

