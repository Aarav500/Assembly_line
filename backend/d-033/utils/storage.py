import json
import os
from typing import Any, Dict, Optional


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def get_attestation_path(storage_dir: str, build_id: str) -> str:
    ensure_dir(storage_dir)
    safe = "".join(c for c in build_id if c.isalnum() or c in ("-", "_", "."))
    return os.path.join(storage_dir, f"{safe}.dsse.json")


def save_json(path: str, data: Dict[str, Any]) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def load_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

