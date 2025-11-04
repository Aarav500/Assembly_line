import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///app.db")
    DEFAULT_MODELS_MODULE: str = os.getenv("MODELS_MODULE", "app.models")
    # Row count mode: none | exact
    ROW_COUNT_MODE: str = os.getenv("ROW_COUNT_MODE", "none")
    # Max tables to count when row_count_mode == exact (to reduce load)
    ROW_COUNT_MAX_TABLES: int = int(os.getenv("ROW_COUNT_MAX_TABLES", "10"))
    INCLUDE_SQL: bool = os.getenv("INCLUDE_SQL", "true").lower() == "true"
    INCLUDE_ALEMBIC_OPS: bool = os.getenv("INCLUDE_ALEMBIC_OPS", "true").lower() == "true"
    APP_NAME: str = os.getenv("APP_NAME", "MigrationAssist")

