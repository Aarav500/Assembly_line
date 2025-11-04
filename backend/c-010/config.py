import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", BASE_DIR / "storage"))

STORAGE = {
    "root": STORAGE_DIR,
    "baselines": STORAGE_DIR / "baselines",
    "snapshots": STORAGE_DIR / "snapshots",
    "diffs": STORAGE_DIR / "diffs",
    "results": STORAGE_DIR / "results",
}

DEFAULT_VIEWPORT = {"width": 1366, "height": 768}
DEFAULT_THRESHOLD = float(os.getenv("DEFAULT_THRESHOLD", 2.0))  # percent mismatch allowed

