import json
import os
from typing import Any, Dict, List


def _ensure_file(file_path: str, default_obj: Any) -> None:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(default_obj, f, indent=2)


def load_ingested_resources(file_path: str) -> List[Dict]:
    _ensure_file(file_path, {"resources": []})
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("resources", [])
    except Exception:
        return []


def upsert_resources(file_path: str, resources: List[Dict]) -> None:
    _ensure_file(file_path, {"resources": []})
    current = load_ingested_resources(file_path)
    by_id: Dict[str, Dict] = {}
    for r in current:
        rid = r.get("id") or f"{r.get('provider')}::{r.get('name')}"
        by_id[rid] = r
    for r in resources:
        rid = r.get("id") or f"{r.get('provider')}::{r.get('name')}"
        by_id[rid] = r
    to_save = {"resources": list(by_id.values())}
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=2)


def save_config(file_path: str, updates: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    data: Dict[str, Any] = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data.update(updates)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

