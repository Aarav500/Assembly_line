import json
import os
import threading
import time
from typing import Dict, Any, List, Optional

from config import DATA_DIR


class Storage:
    def __init__(self):
        self.path = os.path.join(DATA_DIR, "state.json")
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"runs": []}, f)
        self._lock = threading.Lock()

    def _load(self) -> Dict[str, Any]:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: Dict[str, Any]):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.path)

    def list_runs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return self._load().get("runs", [])

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            runs = self._load().get("runs", [])
            for r in runs:
                if r["id"] == run_id:
                    return r
        return None

    def add_run(self, run: Dict[str, Any]):
        with self._lock:
            data = self._load()
            data.setdefault("runs", []).append(run)
            self._save(data)

    def set_run_status(self, run_id: str, status: str):
        with self._lock:
            data = self._load()
            for r in data.get("runs", []):
                if r["id"] == run_id:
                    r["status"] = status
                    r["updated_at"] = time.time()
                    break
            self._save(data)

    def set_run_field(self, run_id: str, key: str, value: Any):
        with self._lock:
            data = self._load()
            for r in data.get("runs", []):
                if r["id"] == run_id:
                    r[key] = value
                    r["updated_at"] = time.time()
                    break
            self._save(data)

    def add_step(self, run_id: str, name: str, status: str, logs: str):
        with self._lock:
            data = self._load()
            for r in data.get("runs", []):
                if r["id"] == run_id:
                    steps = r.setdefault("steps", [])
                    steps.append({"name": name, "status": status, "logs": logs, "started_at": time.time(), "ended_at": None})
                    r["updated_at"] = time.time()
                    break
            self._save(data)

    def update_last_step(self, run_id: str, status: str, logs: str = None):
        with self._lock:
            data = self._load()
            for r in data.get("runs", []):
                if r["id"] == run_id:
                    steps = r.get("steps", [])
                    if not steps:
                        break
                    steps[-1]["status"] = status
                    if logs is not None:
                        steps[-1]["logs"] = logs
                    steps[-1]["ended_at"] = time.time()
                    r["updated_at"] = time.time()
                    break
            self._save(data)

