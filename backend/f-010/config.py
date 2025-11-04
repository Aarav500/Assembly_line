import os
from dataclasses import dataclass


def getenv_bool(key: str, default: bool) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "y", "on")


@dataclass
class Settings:
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", os.path.join(os.getcwd(), "metrics.db"))
    MODEL_STORE_DIR: str = os.getenv("MODEL_STORE_DIR", os.path.join(os.getcwd(), "model_store"))
    DEFAULT_CONTAMINATION: float = float(os.getenv("DEFAULT_CONTAMINATION", "0.05"))
    DEFAULT_ZSCORE_THRESHOLD: float = float(os.getenv("DEFAULT_ZSCORE_THRESHOLD", "3.5"))
    SQLITE_TIMEOUT: int = int(os.getenv("SQLITE_TIMEOUT", "30"))

