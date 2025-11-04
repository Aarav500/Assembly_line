import os

class Config:
    DB_URL = os.getenv("DATABASE_URL", "sqlite:///data/db.sqlite3")
    SANDBOX_PROVIDER = os.getenv("SANDBOX_PROVIDER", "docker_compose")  # docker_compose | mock
    COMPOSE_TEMPLATES_DIR = os.getenv("COMPOSE_TEMPLATES_DIR", "compose-templates")
    SANDBOX_DATA_DIR = os.getenv("SANDBOX_DATA_DIR", "data")
    DEFAULT_TTL_MINUTES = int(os.getenv("DEFAULT_TTL_MINUTES", "60"))
    REAPER_INTERVAL_SECONDS = int(os.getenv("REAPER_INTERVAL_SECONDS", "30"))

