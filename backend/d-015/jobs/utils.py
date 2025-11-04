import json
import os
import time
import subprocess
from datetime import datetime


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)
    return path


def reports_subdir(base: str, name: str):
    path = os.path.join(base, name)
    ensure_dir(base)
    ensure_dir(path)
    return path


def write_json(path: str, data: dict):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    return path


def run_subprocess(cmd, cwd=None):
    start = time.time()
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    end = time.time()
    stdout = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return {
        "returncode": proc.returncode,
        "stdout": stdout,
        "started": datetime.fromtimestamp(start).isoformat(),
        "ended": datetime.fromtimestamp(end).isoformat(),
        "duration_seconds": round(end - start, 3),
    }

