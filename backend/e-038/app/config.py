import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session tokens issued by this service
    SESSION_SIGNING_SECRET = os.environ.get("SESSION_SIGNING_SECRET", "session-secret")
    SESSION_SIGNING_ALG = os.environ.get("SESSION_SIGNING_ALG", "HS256")
    SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "3600"))
    SERVICE_ISSUER = os.environ.get("SERVICE_ISSUER", "urn:identity-federation-service")

    # JWKS and validation
    JWKS_CACHE_TTL = int(os.environ.get("JWKS_CACHE_TTL", "300"))

    # Logging level
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

