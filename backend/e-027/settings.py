import os

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres")
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("1", "true", "yes")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Orchestration
    ADVISORY_LOCK_ID: int = int(os.getenv("ADVISORY_LOCK_ID", "274277832"))
    LONG_TX_MAX_AGE_SECONDS: int = int(os.getenv("LONG_TX_MAX_AGE_SECONDS", "60"))
    REPLICA_MAX_LAG_BYTES: int | None = int(os.getenv("REPLICA_MAX_LAG_BYTES", "0")) or None
    FAIL_ON_UNSAFE: bool = os.getenv("FAIL_ON_UNSAFE", "true").lower() in ("1", "true", "yes")
    PRECHECK_TIMEOUT_SECONDS: int = int(os.getenv("PRECHECK_TIMEOUT_SECONDS", "15"))
    MIGRATION_TIMEOUT_SECONDS: int = int(os.getenv("MIGRATION_TIMEOUT_SECONDS", "600"))
    ALEMBIC_INI_PATH: str = os.getenv("ALEMBIC_INI_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "alembic.ini")))

settings = Settings()

