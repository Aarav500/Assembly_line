import json
import os
import threading
from typing import Optional


class SchemaStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _load(self) -> dict:
        with self._lock:
            with open(self.path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {}
        return data

    def _save_all(self, data: dict):
        with self._lock:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def list_names(self) -> list:
        data = self._load()
        return sorted(list(data.keys()))

    def get(self, name: str) -> Optional[dict]:
        data = self._load()
        return data.get(name)

    def save(self, name: str, schema: dict):
        data = self._load()
        data[name] = schema
        self._save_all(data)

    def delete(self, name: str) -> bool:
        data = self._load()
        if name in data:
            del data[name]
            self._save_all(data)
            return True
        return False

