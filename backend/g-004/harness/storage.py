import os
import json
from typing import Dict, Any, List


class RunStorage:
    def __init__(self, directory: str):
        self.directory = directory
        os.makedirs(self.directory, exist_ok=True)

    def _path(self, run_id: str) -> str:
        return os.path.join(self.directory, f"{run_id}.json")

    def save_run(self, run_id: str, artifact: Dict[str, Any]):
        path = self._path(run_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, ensure_ascii=False, indent=2)

    def load_run(self, run_id: str) -> Dict[str, Any] | None:
        path = self._path(run_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_runs(self) -> List[Dict[str, Any]]:
        runs = []
        for fname in os.listdir(self.directory):
            if not fname.endswith(".json"):
                continue
            rid = fname[:-5]
            try:
                data = self.load_run(rid)
                meta = data.get("metadata", {}) if data else {}
                runs.append({
                    "run_id": rid,
                    "suite": meta.get("suite"),
                    "model": meta.get("model"),
                    "timestamp": meta.get("timestamp"),
                    "path": os.path.join(self.directory, fname)
                })
            except Exception:
                continue
        runs.sort(key=lambda x: (x.get("timestamp") or ""), reverse=True)
        return runs

