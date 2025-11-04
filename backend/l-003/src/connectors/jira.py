import base64
import requests
from typing import Any, Dict
from .base import BaseConnector


class JiraConnector(BaseConnector):
    slug = "jira"
    name = "Jira"

    def _check_enabled(self) -> bool:
        return bool(self.config.get("JIRA_BASE_URL") and self.config.get("JIRA_EMAIL") and self.config.get("JIRA_API_TOKEN"))

    @property
    def _auth(self):
        # Basic auth
        return (self.config.get("JIRA_EMAIL"), self.config.get("JIRA_API_TOKEN"))

    @property
    def _base(self):
        return self.config.get("JIRA_BASE_URL", "").rstrip("/")

    def health(self) -> Dict[str, Any]:
        url = f"{self._base}/rest/api/3/myself"
        r = requests.get(url, auth=self._auth, timeout=10)
        return {"ok": r.status_code == 200, "status_code": r.status_code}

    def search(self, query: str):
        url = f"{self._base}/rest/api/3/search"
        params = {"jql": query, "maxResults": 20}
        r = requests.get(url, auth=self._auth, params=params, timeout=20)
        r.raise_for_status()
        return r.json()

    def get(self, rid: str):
        url = f"{self._base}/rest/api/3/issue/{rid}"
        r = requests.get(url, auth=self._auth, timeout=20)
        if r.status_code == 404:
            return {"error": "Not found", "id": rid}
        r.raise_for_status()
        return r.json()

