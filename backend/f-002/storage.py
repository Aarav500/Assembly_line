import os
import json
import threading
from typing import Optional, Dict, Any, List


class ProjectStore:
    def __init__(self, path: str = "data/projects.json"):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"projects": []}, f, indent=2)

    def _load(self) -> Dict[str, Any]:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: Dict[str, Any]):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.path)

    def list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return self._load().get("projects", [])

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for p in self._load().get("projects", []):
                if p.get("name") == name:
                    return p
        return None

    def add(self, record: Dict[str, Any]):
        with self._lock:
            data = self._load()
            projects = data.get("projects", [])
            for p in projects:
                if p.get("name") == record.get("name"):
                    raise ValueError("Project exists")
            projects.append(record)
            data["projects"] = projects
            self._save(data)

    def update(self, name: str, record: Dict[str, Any]):
        with self._lock:
            data = self._load()
            projects = data.get("projects", [])
            for i, p in enumerate(projects):
                if p.get("name") == name:
                    projects[i] = record
                    data["projects"] = projects
                    self._save(data)
                    return
            raise KeyError("Project not found")

    def remove(self, name: str):
        with self._lock:
            data = self._load()
            projects = [p for p in data.get("projects", []) if p.get("name") != name]
            data["projects"] = projects
            self._save(data)

