import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path: str, content: bytes):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=directory) as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name
    os.replace(tmp_path, path)


def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def dump_json(path: str, obj):
    data = json.dumps(obj, ensure_ascii=False, indent=2)
    atomic_write(path, data.encode("utf-8"))


def path_to_output_file(path: str) -> str:
    # Normalize to leading slash
    if not path.startswith("/"):
        path = "/" + path
    # Remove query and fragments if any (should not be present)
    clean = path.split("?")[0].split("#")[0]
    if clean.endswith("/"):
        clean = clean[:-1]
    if clean == "":
        clean = "/"
    # If it's root or no extension, output as dir/index.html
    if clean == "/":
        return os.path.join("index.html")
    if "." in os.path.basename(clean):
        # Has an extension, return as-is without leading slash
        return clean.lstrip("/")
    # Else build dir/index.html
    return os.path.join(clean.lstrip("/"), "index.html")

