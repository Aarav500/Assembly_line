import os
import requests
from typing import Any, Dict
from .base import BaseConnector


class NotionConnector(BaseConnector):
    slug = "notion"
    name = "Notion"

    def _check_enabled(self) -> bool:
        return bool(self.config.get("NOTION_TOKEN"))

    @property
    def _headers(self):
        return {
            "Authorization": f"Bearer {self.config.get('NOTION_TOKEN')}",
            "Notion-Version": self.config.get("NOTION_VERSION", "2022-06-28"),
            "Content-Type": "application/json",
        }

    @property
    def _base(self):
        return "https://api.notion.com/v1"

    def health(self) -> Dict[str, Any]:
        # Notion doesn't have a direct ping; do a lightweight search for empty query
        url = f"{self._base}/search"
        r = requests.post(url, headers=self._headers, json={"page_size": 1}, timeout=10)
        ok = r.status_code == 200
        return {"ok": ok, "status_code": r.status_code}

    def search(self, query: str):
        url = f"{self._base}/search"
        payload = {"query": query, "page_size": 10}
        r = requests.post(url, headers=self._headers, json=payload, timeout=15)
        r.raise_for_status()
        return r.json()

    def get(self, rid: str):
        # Try page first, then database
        for kind in ["pages", "databases"]:
            url = f"{self._base}/{kind}/{rid}"
            rr = requests.get(url, headers=self._headers, timeout=15)
            if rr.status_code == 200:
                return rr.json()
        return {"error": "Not found", "id": rid}

    # Extra actions
    def op_get_block_children(self, block_id: str, page_size: int = 50):
        url = f"{self._base}/blocks/{block_id}/children?page_size={page_size}"
        r = requests.get(url, headers=self._headers, timeout=15)
        r.raise_for_status()
        return r.json()

