import time
import requests
from typing import Optional


def is_url_healthy(url: str, timeout: float = 3.0, retries: int = 1) -> bool:
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout)
            if 200 <= resp.status_code < 300:
                return True
        except Exception as e:
            last_exc = e
        time.sleep(0.2)
    return False

