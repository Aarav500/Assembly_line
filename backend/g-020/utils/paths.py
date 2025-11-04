import json
import os
import zipfile
from typing import Any


ARTIFACTS_ROOT = os.environ.get("ARTIFACTS_ROOT", "artifacts")


def get_artifacts_root() -> str:
    os.makedirs(ARTIFACTS_ROOT, exist_ok=True)
    return ARTIFACTS_ROOT


def make_artifact_dir(prefix: str) -> str:
    root = get_artifacts_root()
    i = 0
    while True:
        name = f"{prefix}-{i}" if i else prefix
        path = os.path.join(root, name)
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            return path
        i += 1


def save_json(path: str, obj: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def zip_dir(src_dir: str, zip_path: str) -> str:
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(src_dir):
            for fn in files:
                full = os.path.join(root, fn)
                arc = os.path.relpath(full, src_dir)
                zf.write(full, arc)
    return zip_path

