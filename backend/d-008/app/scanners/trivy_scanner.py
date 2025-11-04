import json
import os
import shlex
import subprocess
from typing import Any, Dict, Optional


class TrivyScanner:
    def __init__(self, trivy_path: str = "trivy", timeout: int = 900):
        self.trivy_path = trivy_path
        self.timeout = timeout

    def _run(self, args: list[str], env: Optional[dict] = None) -> Dict[str, Any]:
        cmd = [self.trivy_path] + args
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, **(env or {})},
                timeout=self.timeout,
                check=False,
                text=True,
            )
        except FileNotFoundError:
            raise RuntimeError("Trivy CLI not found. Install trivy or set TRIVY_PATH.")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Trivy scan timed out")

        if proc.returncode not in (0, 5, 1):
            # Trivy uses non-zero for findings too (5), but other non-zero can be errors
            err_msg = proc.stderr.strip() or proc.stdout.strip()
            raise RuntimeError(f"Trivy failed (code {proc.returncode}): {err_msg}")

        out = proc.stdout.strip() or "{}"
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            # Fallback if trivy outputs non-JSON
            raise RuntimeError("Trivy did not return JSON output. Ensure --format json is supported.")

    def scan_filesystem(self, path: str, severity: Optional[str] = None, include_config_scan: bool = True) -> Dict[str, Any]:
        # security-checks can include: vuln, config, secret, license (license in recent versions)
        checks = ["vuln"]
        if include_config_scan:
            checks.append("config")
        args = [
            "fs",
            "--quiet",
            "--format", "json",
            "--security-checks", ",".join(checks),
            "--skip-dirs", ".git,.svn,.hg,.tox,node_modules,venv,.venv,.mypy_cache,.pytest_cache",
        ]
        if severity:
            args += ["--severity", severity]
        args.append(path)
        return self._run(args)

    def scan_image(self, image: str, severity: Optional[str] = None) -> Dict[str, Any]:
        args = [
            "image",
            "--quiet",
            "--format", "json",
            "--security-checks", "vuln,config",
        ]
        if severity:
            args += ["--severity", severity]
        args.append(image)
        return self._run(args)

