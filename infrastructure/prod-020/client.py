import os
from typing import Any, Dict, Optional

import requests


class FeatureFlagsClient:
    def __init__(self, base_url: str | None = None, timeout: float = 2.0):
        self.base_url = base_url or os.getenv("FF_SERVICE_URL", "http://localhost:5000")
        self.timeout = timeout

    def get_flag(self, name: str) -> Optional[Dict[str, Any]]:
        r = requests.get(f"{self.base_url}/flags/{name}", timeout=self.timeout)
        if r.status_code == 200:
            return r.json()
        return None

    def decide(self, flag_name: str, user_id: str) -> Dict[str, Any]:
        r = requests.get(f"{self.base_url}/decide/{flag_name}", params={"user_id": user_id}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def get_experiment(self, name: str) -> Optional[Dict[str, Any]]:
        r = requests.get(f"{self.base_url}/experiments/{name}", timeout=self.timeout)
        if r.status_code == 200:
            return r.json()
        return None

    def assign(self, experiment: str, user_id: str) -> Dict[str, Any]:
        r = requests.get(f"{self.base_url}/assign/{experiment}", params={"user_id": user_id}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

