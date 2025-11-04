from __future__ import annotations
import json
import os
import threading
from typing import Any, Dict, Optional


class IssueRegistry:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._ensure()

    def _ensure(self):
        directory = os.path.dirname(self.path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"items": {}}, f)

    def _load(self) -> Dict[str, Any]:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: Dict[str, Any]):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.path)

    def get(self, gap_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._load()
            return data.get("items", {}).get(gap_id)

    def put(self, gap_id: str, issue_id: Any, issue_url: str | None):
        with self._lock:
            data = self._load()
            items = data.setdefault("items", {})
            items[gap_id] = {"issue_id": issue_id, "issue_url": issue_url}
            self._save(data)

