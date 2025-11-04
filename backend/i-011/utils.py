import os
import base64
import time
import uuid
from datetime import datetime, timezone

def now_ts() -> float:
    return time.time()

def to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

def uuid_str() -> str:
    return str(uuid.uuid4())

def random_secret(nbytes: int = 32) -> str:
    return base64.urlsafe_b64encode(os.urandom(nbytes)).decode('ascii').rstrip('=')

