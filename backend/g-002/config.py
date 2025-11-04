import os
from pathlib import Path

BASE_DIR = Path(os.getenv("APP_BASE_DIR", ".")).resolve()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = str(DATA_DIR / os.getenv("DB_FILENAME", "app.db"))
CHECKPOINT_DIR = str(DATA_DIR / "checkpoints")
LOG_DIR = str(DATA_DIR / "logs")

# Orchestration
MIN_WORKERS = int(os.getenv("MIN_WORKERS", "1"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
QUEUE_POLL_INTERVAL_SEC = float(os.getenv("QUEUE_POLL_INTERVAL_SEC", "2.0"))
SCALE_INTERVAL_SEC = float(os.getenv("SCALE_INTERVAL_SEC", "3.0"))

# Retry policy
BACKOFF_BASE_SECONDS = float(os.getenv("BACKOFF_BASE_SECONDS", "5"))
BACKOFF_MAX_SECONDS = float(os.getenv("BACKOFF_MAX_SECONDS", "300"))
JITTER_SECONDS = float(os.getenv("JITTER_SECONDS", "1.0"))

# Training simulation
DEFAULT_EPOCHS = int(os.getenv("DEFAULT_EPOCHS", "10"))
DEFAULT_CHECKPOINT_INTERVAL = int(os.getenv("DEFAULT_CHECKPOINT_INTERVAL", "2"))
DEFAULT_MAX_RETRIES = int(os.getenv("DEFAULT_MAX_RETRIES", "3"))

# Ensure directories
Path(CHECKPOINT_DIR).mkdir(parents=True, exist_ok=True)
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

