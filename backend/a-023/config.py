import os

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///audit.db")
    DEBUG = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
    JSON_SORT_KEYS = False

