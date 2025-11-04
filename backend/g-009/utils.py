import json
import time
import hashlib
from datetime import datetime, timezone


def hash_request(payload: dict) -> str:
    """Stable SHA256 hash of a JSON-serializable payload."""
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()

