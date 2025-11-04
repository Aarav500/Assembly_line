import requests
from typing import Any, Dict
from .base import BaseConnector


class FigmaConnector(BaseConnector):
    slug = "figma"
    name = "Figma"

    def _check_enabled(self) -> bool:
        return bool(self.config.get("FIGMA_TOKEN"))

    @property
    def _headers(self):
        return {"X-Figma-Token": self.config.get("FIGMA_TOKEN")}

    @property
    def _base(self):
        return "https://api.figma.com/v1"

    def health(self) -> Dict[str, Any]:
        # No ping; try me endpoint via a small call (files endpoint needs key). We'll call teams/search with empty query which returns 400; treat 401/403 as not ok.
        url = f"{self._base}/projects/0/files"  # will 404; we only test auth header acceptance via status code not 401
        r = requests.get(url, headers=self._headers, timeout=10)
        return {"ok": r.status_code in (200, 400, 404), "status_code": r.status_code}

    def search(self, query: str):
        url = f"{self._base}/search"
        params = {"query": query}
        r = requests.get(url, headers=self._headers, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def op_get_file(self, file_key: str):
        url = f"{self._base}/files/{file_key}"
        r = requests.get(url, headers=self._headers, timeout=20)
        r.raise_for_status()
        return r.json()

