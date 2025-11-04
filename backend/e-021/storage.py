import json
import os
import uuid
from typing import Dict, Any, List

class DriftStorage:
    def __init__(self, config):
        self.dir = config.DRIFT_REPORT_DIR
        os.makedirs(self.dir, exist_ok=True)

    def _path_for(self, rid: str) -> str:
        return os.path.join(self.dir, f"{rid}.json")

    def save_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        rid = uuid.uuid4().hex
        report = dict(report)
        report["id"] = rid
        with open(self._path_for(rid), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, sort_keys=False)
        return report

    def list_reports(self) -> List[Dict[str, Any]]:
        items = []
        for fname in sorted(os.listdir(self.dir)):
            if not fname.endswith('.json'):
                continue
            try:
                with open(os.path.join(self.dir, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Provide summary
                    items.append({
                        "id": data.get("id"),
                        "timestamp": data.get("timestamp"),
                        "summary": data.get("summary"),
                    })
            except Exception:
                continue
        items.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        return items

    def load_report(self, rid: str) -> Dict[str, Any]:
        path = self._path_for(rid)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

