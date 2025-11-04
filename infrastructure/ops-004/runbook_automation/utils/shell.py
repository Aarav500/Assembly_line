import subprocess
import os
from typing import Dict, Any, List, Optional


def run(cmd: List[str], env: Optional[dict] = None, timeout: Optional[int] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env or os.environ.copy(), cwd=cwd)
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "cmd": cmd,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "returncode": -1,
            "stdout": e.stdout or "",
            "stderr": (e.stderr or "") + f"\nTimeoutExpired after {timeout}s",
            "cmd": cmd,
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "cmd": cmd,
        }

