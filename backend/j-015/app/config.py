import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-please")

    # Rate limiting
    RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "200"))
    RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "900"))  # 15 min

    # Security header toggles
    ENABLE_HSTS = os.environ.get("ENABLE_HSTS", "1") == "1"
    HSTS_MAX_AGE = int(os.environ.get("HSTS_MAX_AGE", "31536000"))
    CONTENT_SECURITY_POLICY = (
        os.environ.get(
            "CONTENT_SECURITY_POLICY",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'",
        )
    )
    REFERRER_POLICY = os.environ.get("REFERRER_POLICY", "no-referrer")
    PERMISSIONS_POLICY = os.environ.get(
        "PERMISSIONS_POLICY",
        "geolocation=(), camera=(), microphone=(), payment=()",
    )

    # App metadata
    APP_NAME = os.environ.get("APP_NAME", "Recommendations Hub")
    APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")

