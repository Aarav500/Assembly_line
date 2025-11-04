import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, Optional

SAFE_BASE = Path("environments").resolve()

def run_cmd(cmd: list[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError as e:
        return 127, "", str(e)

def safe_rmtree(path: Path):
    try:
        rp = Path(path).resolve()
        if not str(rp).startswith(str(SAFE_BASE)):
            raise ValueError("Refusing to delete path outside SAFE_BASE")
        if rp.exists():
            shutil.rmtree(rp)
    except Exception:
        # best effort cleanup; ignore errors
        pass

def sanitize_int(value) -> int:
    try:
        i = int(value)
        if i < 0:
            return 0
        return i
    except Exception:
        return 0

