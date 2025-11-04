import json
import os
from typing import Optional

from config import DATA_DIR


class Registry:
    def __init__(self, path: str = None):
        self.path = path or os.path.join(DATA_DIR, "registry.json")
        self._data = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except json.JSONDecodeError:
            self._data = {}

    def latest_for_channel(self, image: str, channel: str) -> Optional[str]:
        # Keyed by f"{image}:{channel}" -> {"latest": tag}
        key = f"{image}:{channel}"
        rec = self._data.get(key)
        if rec:
            return rec.get("latest")
        return None


class VulnRegistry:
    def __init__(self, path: str = None):
        self.path = path or os.path.join(DATA_DIR, "vulns.json")
        self._data = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except json.JSONDecodeError:
            self._data = {}

    def get(self, image_with_tag: str) -> dict:
        return self._data.get(image_with_tag, {"critical": 0, "high": 0})

