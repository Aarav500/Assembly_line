import os

class Config:
    # Example: postgresql+psycopg2://user:pass@localhost:5432/multitenant
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/multitenant",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PROPAGATE_EXCEPTIONS = True

    # Tenant resolution
    TENANT_HEADER = os.getenv("TENANT_HEADER", "X-Tenant")
    TENANT_DEFAULT = os.getenv("TENANT_DEFAULT")  # Optional default tenant id
    TENANT_SCHEMA_PREFIX = os.getenv("TENANT_SCHEMA_PREFIX", "t_")

class TestConfig(Config):
    TESTING = True

