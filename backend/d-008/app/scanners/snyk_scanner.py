import json
import os
import subprocess
from typing import Any, Dict, Optional


class SnykScanner:
    def __init__(self, snyk_path: str = "snyk", snyk_token: Optional[str] = None, timeout: int = 900):
        self.snyk_path = snyk_path
        self.snyk_token = snyk_token or os.getenv("SNYK_TOKEN")
        self.timeout = timeout

    def _ensure_auth_env(self) -> dict:
        env = dict(os.environ)
        if self.snyk_token:
            env["SNYK_TOKEN"] = self.snyk_token
        return env

    def _run(self, args: list[str]) -> Dict[str, Any]:
        cmd = [self.snyk_path] + args
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._ensure_auth_env(),
                timeout=self.timeout,
                check=False,
                text=True,
            )
        except FileNotFoundError:
            raise RuntimeError("Snyk CLI not found. Install snyk or set SNYK_PATH.")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Snyk scan timed out")

        # Snyk returns non-zero when vulns found. We'll accept outputs if JSON parses.
        out = proc.stdout.strip()
        if not out:
            err = proc.stderr.strip()
            # If unauthenticated or other errors
            if "authentication" in err.lower() or "auth" in err.lower():
                raise RuntimeError("Snyk authentication failed or SNYK_TOKEN missing.")
            raise RuntimeError(f"Snyk CLI error: {err}")

        try:
            return json.loads(out)
        except json.JSONDecodeError:
            raise RuntimeError("Snyk did not return JSON output. Ensure --json flag is supported.")

    def scan_filesystem(self, path: str) -> Dict[str, Any]:
        # 'snyk test' auto-detects ecosystems in a directory
        args = [
            "test",
            "--json",
            path,
        ]
        return self._run(args)

    def scan_image(self, image: str) -> Dict[str, Any]:
        # For containers, Snyk recommends `snyk container test` command
        args = [
            "container", "test", image, "--json",
        ]
        return self._run(args)

