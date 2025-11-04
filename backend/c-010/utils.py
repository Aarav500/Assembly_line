import os
import re
import glob
import json
from datetime import datetime
from pathlib import Path
from typing import Any, List

from config import STORAGE


def ensure_storage():
    for key, path in STORAGE.items():
        if isinstance(path, Path):
            path.mkdir(parents=True, exist_ok=True)


def timestamp_str():
    return datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")


def safe_name(name: str) -> str:
    name = name.strip().lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9._-]", "-", name)


def save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def list_sorted_by_mtime(pattern: str) -> List[str]:
    files = glob.glob(pattern)
    files.sort(key=lambda p: Path(p).stat().st_mtime)
    return files

