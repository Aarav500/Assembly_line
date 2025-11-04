from typing import Dict, Any, Optional
import requests


class StandardClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def infer(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/infer"
        resp = requests.post(url, json=payload, timeout=self.timeout, headers=headers or {})
        resp.raise_for_status()
        return resp.json()

