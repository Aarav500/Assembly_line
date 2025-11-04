import os
import json
import tempfile
import threading
from typing import Dict, Any, Optional, List


class Storage:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._lock = threading.Lock()
        # ensure directory exists
        parent = os.path.dirname(os.path.abspath(self.file_path))
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

    def exists(self) -> bool:
        return os.path.exists(self.file_path)

    def load(self) -> Dict[str, Any]:
        with self._lock:
            if not os.path.exists(self.file_path):
                return {"runners": [], "policy": {}}
            with open(self.file_path, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {"runners": [], "policy": {}}

    def save(self, data: Dict[str, Any]) -> None:
        with self._lock:
            tmp_fd, tmp_path = tempfile.mkstemp(prefix="ci-routing-", suffix=".json")
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tf:
                    json.dump(data, tf, indent=2, sort_keys=True)
                os.replace(tmp_path, self.file_path)
            finally:
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass

    def add_runner(self, runner: Dict[str, Any]) -> Dict[str, Any]:
        data = self.load()
        data.setdefault("runners", [])
        data["runners"].append(runner)
        self.save(data)
        return runner

    def update_runner(self, runner_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = self.load()
        runners: List[Dict[str, Any]] = data.get("runners", [])
        updated: Optional[Dict[str, Any]] = None
        for r in runners:
            if r.get("id") == runner_id:
                for k, v in updates.items():
                    if k in {"id"}:
                        continue
                    r[k] = v
                updated = r
                break
        if updated is not None:
            self.save(data)
        return updated

    def delete_runner(self, runner_id: str) -> bool:
        data = self.load()
        runners: List[Dict[str, Any]] = data.get("runners", [])
        new_runners = [r for r in runners if r.get("id") != runner_id]
        if len(new_runners) == len(runners):
            return False
        data["runners"] = new_runners
        self.save(data)
        return True

    def set_policy(self, policy: Dict[str, Any]) -> None:
        data = self.load()
        data["policy"] = policy
        self.save(data)

