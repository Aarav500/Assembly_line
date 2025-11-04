import os
import json
from typing import Dict, Any, List


REQUIRED_FIELDS = ["name", "items"]


def validate_suite(suite: Dict[str, Any]):
    for f in REQUIRED_FIELDS:
        if f not in suite:
            raise ValueError(f"Suite missing required field: {f}")
    if not isinstance(suite["items"], list) or not suite["items"]:
        raise ValueError("Suite 'items' must be a non-empty array")


class SuiteRepository:
    def __init__(self, directory: str):
        self.directory = directory
        os.makedirs(self.directory, exist_ok=True)

    def list_suites(self) -> List[Dict[str, Any]]:
        suites = []
        for fname in os.listdir(self.directory):
            if not fname.endswith(".json"):
                continue
            try:
                suite = self.get_suite(fname[:-5])
                if suite:
                    suites.append({"name": suite.get("name"), "description": suite.get("description", ""), "task_type": suite.get("task_type", ""), "num_items": len(suite.get("items", []))})
            except Exception:
                continue
        return sorted(suites, key=lambda x: x["name"])

    def get_suite(self, name: str) -> Dict[str, Any] | None:
        path = os.path.join(self.directory, f"{name}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            suite = json.load(f)
        return suite

    def save_suite(self, suite: Dict[str, Any]) -> Dict[str, Any]:
        validate_suite(suite)
        name = suite["name"]
        path = os.path.join(self.directory, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(suite, f, ensure_ascii=False, indent=2)
        return {"name": name, "path": path}

