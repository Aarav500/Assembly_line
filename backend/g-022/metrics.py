import json
import os
import threading
import time
from typing import Any, Dict

from config import LOG_DIR

_lock = threading.Lock()
_log_file_path = None


def _ensure_log_file():
    global _log_file_path
    if _log_file_path is None:
        os.makedirs(LOG_DIR, exist_ok=True)
        _log_file_path = os.path.join(LOG_DIR, "metrics.log")
    return _log_file_path


def log_prediction(event: Dict[str, Any]) -> None:
    # Ensure a timestamp exists
    payload = dict(event)
    payload.setdefault("ts", int(time.time() * 1000))
    line = json.dumps(payload, separators=(",", ":"))
    path = _ensure_log_file()
    try:
        with _lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        # Fallback to stdout if file logging fails
        print(line)

