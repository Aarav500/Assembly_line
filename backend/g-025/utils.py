import os
import sys
import json
import hashlib
import shutil
import subprocess
import platform
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import random

import numpy as np


EXCLUDES = {
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "experiments",  # do not recursively include previous experiments
}


def ensure_dir(path: Path):
    Path(path).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, obj: Dict[str, Any]):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def read_json(path: Path) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch  # optional
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except Exception:
        pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _iter_code_files(root_dir: Path):
    root_dir = Path(root_dir)
    for base, dirs, files in os.walk(root_dir):
        # Prune excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDES and not d.startswith(".")]
        for fn in files:
            if fn.endswith((".py", ".toml", ".cfg", ".ini", ".txt", ".md", ".json", ".yaml", ".yml")):
                full = Path(base) / fn
                # Skip files inside excluded dirs just in case
                if any(part in EXCLUDES for part in full.parts):
                    continue
                yield full


def snapshot_code(root_dir: Path, dest_dir: Path) -> Dict[str, Any]:
    root_dir = Path(root_dir).resolve()
    dest_dir = Path(dest_dir).resolve()
    ensure_dir(dest_dir)
    manifest = {
        "root": str(root_dir),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "files": [],
    }

    for src in _iter_code_files(root_dir):
        try:
            rel = src.relative_to(root_dir)
        except ValueError:
            # If not relative, skip
            continue
        # Do not copy into itself
        dest = dest_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        file_hash = sha256_file(src)
        manifest["files"].append({
            "path": str(rel),
            "sha256": file_hash,
            "size": os.path.getsize(src),
        })

    # Sort manifest by path for determinism
    manifest["files"].sort(key=lambda x: x["path"])
    manifest_hash = sha256_bytes(json.dumps(manifest, sort_keys=True).encode("utf-8"))
    manifest["manifest_sha256"] = manifest_hash
    return manifest


def zip_dir(src_dir: Path, zip_path: Path):
    src_dir = Path(src_dir)
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    # Use shutil.make_archive requires base_name without extension
    base_name = str(zip_path.with_suffix(""))
    root_dir = str(src_dir)
    # Create archive in a temp location then move to zip_path
    tmp_base = base_name + ".tmp"
    archive_path = shutil.make_archive(tmp_base, "zip", root_dir=root_dir, base_dir=".")
    shutil.move(archive_path, zip_path)


def capture_environment(exp_dir: Path):
    env_dir = Path(exp_dir) / "environment"
    ensure_dir(env_dir)
    # python version
    with open(env_dir / "python_version.txt", "w", encoding="utf-8") as f:
        f.write(sys.version + "\n")
    # platform info
    plat = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
    }
    write_json(env_dir / "platform.json", plat)
    # pip freeze
    try:
        out = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], stderr=subprocess.STDOUT, text=True)
    except Exception as e:
        out = f"<pip freeze failed: {e}>\n"
    with open(env_dir / "requirements.freeze.txt", "w", encoding="utf-8") as f:
        f.write(out)
    # copy requirements.txt if present at root
    root_req = Path.cwd() / "requirements.txt"
    if root_req.exists():
        shutil.copy2(root_req, env_dir / "requirements.txt")


def collect_git_info(root_dir: Path) -> Dict[str, Any]:
    root_dir = Path(root_dir)
    def _cmd(args):
        try:
            return subprocess.check_output(args, cwd=root_dir, stderr=subprocess.STDOUT, text=True).strip()
        except Exception:
            return None
    info = {
        "commit": _cmd(["git", "rev-parse", "HEAD"]),
        "branch": _cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "status_porcelain": _cmd(["git", "status", "--porcelain"]),
        "remote": _cmd(["git", "remote", "-v"]),
        "is_dirty": None,
    }
    if info["status_porcelain"] is not None:
        info["is_dirty"] = len(info["status_porcelain"].strip()) > 0
    return info

