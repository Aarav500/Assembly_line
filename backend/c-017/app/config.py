import os
from datetime import timedelta


def getenv_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "on"}


class Config:
    ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = getenv_bool("DEBUG", True)
    TESTING = getenv_bool("TESTING", False)
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", os.getenv("SECRET_KEY", "dev-jwt-secret"))
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_EXPIRES = int(os.getenv("JWT_ACCESS_EXPIRES", str(int(timedelta(hours=1).total_seconds()))))
    JWT_REFRESH_EXPIRES = int(os.getenv("JWT_REFRESH_EXPIRES", str(int(timedelta(days=30).total_seconds()))))
    JWT_ISSUER = os.getenv("JWT_ISSUER", "auth-rbac-scaffold")

    # OAuth/OIDC connectors
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

    OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID")
    OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET")
    OIDC_SERVER_METADATA_URL = os.getenv("OIDC_SERVER_METADATA_URL")

    # App behavior
    AUTO_CREATE_DB = getenv_bool("AUTO_CREATE_DB", True)
    SEED_DB = getenv_bool("SEED_DB", True)

    # Admin bootstrap
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin123!")

    PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "http")

