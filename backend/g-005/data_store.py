import json
import os
from typing import List, Dict, Any
from threading import RLock


class DataStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = RLock()
        self._data = {"labeled": [], "unlabeled": [], "test": []}
        self._load_or_init()

    def _load_or_init(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        self._reload()

    def _reload(self):
        with self._lock:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
                # normalize ids to int if possible
                for key in ["labeled", "unlabeled", "test"]:
                    for item in self._data.get(key, []):
                        try:
                            item["id"] = int(item["id"])
                        except Exception:
                            pass

    def save(self):
        with self._lock:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get_labeled(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._data.get("labeled", []))

    def get_unlabeled(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._data.get("unlabeled", []))

    def get_test(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._data.get("test", []))

    def update_label(self, sample_id: int, label: str) -> bool:
        with self._lock:
            # If exists in labeled, update
            for item in self._data["labeled"]:
                if item["id"] == sample_id:
                    item["label"] = label
                    return True
            # Else move from unlabeled to labeled
            for i, item in enumerate(self._data["unlabeled"]):
                if item["id"] == sample_id:
                    self._data["unlabeled"].pop(i)
                    self._data["labeled"].append({"id": sample_id, "text": item["text"], "label": label})
                    return True
        return False

    def add_unlabeled(self, items: List[Dict[str, Any]]):
        with self._lock:
            existing_ids = set([x["id"] for x in self._data["unlabeled"]]) | set([x["id"] for x in self._data["labeled"]])
            for it in items:
                if it["id"] not in existing_ids:
                    self._data["unlabeled"].append({"id": it["id"], "text": it["text"]})

    def get_counts(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "labeled": len(self._data.get("labeled", [])),
                "unlabeled": len(self._data.get("unlabeled", [])),
                "test": len(self._data.get("test", [])),
            }

