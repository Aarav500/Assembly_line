import json
import os
import re
import shutil
import signal
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Callable, Any
import click


LIFECYCLE_DIR = ".lifecycle"
RELEASES_SUBDIR = "releases"
LOGS_SUBDIR = "logs"
META_FILE = "deployments.json"


def now_ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def echo_info(msg: str):
    click.secho(msg, fg="green")


def echo_warn(msg: str):
    click.secho(msg, fg="yellow")


def echo_err(msg: str):
    click.secho(msg, fg="red", err=True)


def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


@dataclass
class ProjectPaths:
    root: Path

    @property
    def lifecycle(self) -> Path:
        return self.root / LIFECYCLE_DIR

    @property
    def releases(self) -> Path:
        return self.lifecycle / RELEASES_SUBDIR

    @property
    def logs(self) -> Path:
        return self.lifecycle / LOGS_SUBDIR

    @property
    def meta(self) -> Path:
        return self.lifecycle / META_FILE


EXCLUDE_PATTERNS = [
    re.compile(p) for p in [
        r"^\.lifecycle$",
        r"^\.git$",
        r"^__pycache__$",
        r"^\.venv$",
        r"^\.mypy_cache$",
        r"^\.pytest_cache$",
        r"^\.DS_Store$",
        r"^env$",
        r"^venv$",
    ]
]


def should_exclude(name: str) -> bool:
    return any(p.match(name) for p in EXCLUDE_PATTERNS)


def copytree(src: Path, dst: Path):
    if dst.exists():
        raise FileExistsError(f"Destination already exists: {dst}")
    dst.mkdir(parents=True, exist_ok=False)
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        # filter directories
        dirs[:] = [d for d in dirs if not should_exclude(d)]
        for d in dirs:
            (dst / rel / d).mkdir(parents=True, exist_ok=True)
        for f in files:
            if should_exclude(f):
                continue
            src_file = Path(root) / f
            dst_file = dst / rel / f
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)


def kill_pid(pid: int) -> bool:
    try:
        if sys.platform.startswith("win"):
            os.kill(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    except Exception:
        return False


def is_process_running(pid: int) -> bool:
    try:
        if pid <= 0:
            return False
        # Sending signal 0 does not kill, but tests existence
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def find_flask_entry(root: Path) -> tuple[str, Path]:
    """Find a Flask app entry script and module name. Defaults to app.py."""
    candidates = ["app.py", "main.py", "wsgi.py"]
    for name in candidates:
        p = root / name
        if p.exists():
            mod = p.stem
            return mod, p
    # fallback: any file containing "Flask("
    for py in root.glob("*.py"):
        try:
            txt = py.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "Flask(" in txt:
            return py.stem, py
    raise FileNotFoundError("No Flask entry script found (looked for app.py/main.py/wsgi.py)")

