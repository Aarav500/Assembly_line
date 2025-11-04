import os
from dataclasses import dataclass


@dataclass
class Settings:
    DB_URL: str = os.environ.get("DB_URL", "sqlite:///./data.sqlite")
    WORKSPACE_DIR: str = os.environ.get("WORKSPACE_DIR", os.path.abspath("./workspace"))

    # Analysis tuning
    SHINGLE_SIZE: int = int(os.environ.get("SHINGLE_SIZE", 4))
    JACCARD_THRESHOLD: float = float(os.environ.get("JACCARD_THRESHOLD", 0.6))
    MAX_FUNCTION_SIZE_LINES: int = int(os.environ.get("MAX_FUNCTION_SIZE_LINES", 1000))

