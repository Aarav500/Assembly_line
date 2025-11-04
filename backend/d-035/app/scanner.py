import json
import shutil
import subprocess
from typing import Dict, Any, Tuple

from .config import settings


class ScanError(Exception):
    pass


class BaseScanner:
    name = "base"

    def scan_image(self, image: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
        raise NotImplementedError


def _count_severities_from_trivy(report: Dict[str, Any]) -> Dict[str, int]:
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
    results = report.get("Results") or []
    for r in results:
        vulns = r.get("Vulnerabilities") or []
        for v in vulns:
            sev = (v.get("Severity") or "UNKNOWN").upper()
            if sev not in counts:
                sev = "UNKNOWN"
            counts[sev] += 1
    return counts


class TrivyScanner(BaseScanner):
    name = "trivy"

    def __init__(self, trivy_path: str | None = None, timeout: int | None = None) -> None:
        self.trivy_path = trivy_path or settings.trivy_path
        self.timeout = timeout or settings.trivy_timeout
        self._ensure_available()

    def _ensure_available(self) -> None:
        if not shutil.which(self.trivy_path):
            raise ScanError(f"Trivy not found at path: {self.trivy_path}")

    def scan_image(self, image: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
        cmd = [
            self.trivy_path,
            "image",
            "--quiet",
            "--format",
            "json",
            "--ignore-unfixed",
            image,
        ]
        try:
            completed = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                check=False,
                text=True,
            )
        except subprocess.TimeoutExpired as e:
            raise ScanError(f"Trivy scan timed out for {image}: {e}")

        if completed.returncode not in (0, 1):
            # Trivy returns 0 when no vulns, 1 when vulns found; other codes are errors
            raise ScanError(
                f"Trivy failed for {image} (code {completed.returncode}): {completed.stderr.strip()}"
            )

        try:
            report = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as e:
            raise ScanError(f"Invalid JSON from trivy for {image}: {e}")

        counts = _count_severities_from_trivy(report)
        return report, counts


class MockScanner(BaseScanner):
    name = "mock"

    def scan_image(self, image: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
        report: Dict[str, Any] = {
            "ArtifactName": image,
            "Results": [],
            "Summary": {"note": "Mock scanner in use; no vulnerabilities reported."},
        }
        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
        return report, counts


def get_scanner() -> BaseScanner:
    name = (settings.scanner or "trivy").lower()
    if name == "trivy":
        try:
            return TrivyScanner()
        except ScanError:
            # Fallback to mock if trivy not available
            return MockScanner()
    if name == "mock":
        return MockScanner()
    # Default fallback
    return MockScanner()

