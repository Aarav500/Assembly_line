import os
import socket
import subprocess
import sys
import time
from contextlib import closing
from typing import Tuple

import requests


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def _wait_for_health(base_url: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    url = f"{base_url}/health"
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200 and r.json().get("status") == "ok":
                return True
        except Exception as e:
            last_err = e
        time.sleep(0.5)
    if last_err:
        print(f"Health check failed: {last_err}", file=sys.stderr)
    return False


def run_smoke_tests() -> Tuple[bool, str]:
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["SANDBOX_MODE"] = "1"
    env["BASE_URL"] = base_url

    # Start the app server in sandbox mode
    proc = subprocess.Popen(
        [sys.executable, "run_server.py", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    try:
        if not _wait_for_health(base_url, timeout=40.0):
            # Read some logs for context
            try:
                out = proc.stdout.read(5000) if proc.stdout else ""
            except Exception:
                out = ""
            return False, f"App failed health check on {base_url}. Logs: {out}"

        # Run smoke tests
        print(f"Running smoke tests against {base_url}")
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/smoke"], env=env, text=True)
        if result.returncode == 0:
            return True, "ok"
        return False, f"pytest exit code {result.returncode}"
    finally:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass


if __name__ == "__main__":
    ok, report = run_smoke_tests()
    print("SMOKE_RESULT:", "PASS" if ok else "FAIL", report)
    sys.exit(0 if ok else 1)

