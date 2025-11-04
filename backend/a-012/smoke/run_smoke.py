from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable

import requests
from werkzeug.serving import make_server


# --------------------------- Local server utility ---------------------------
class LocalServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 5001):
        self.host = host
        self.port = port
        self._srv = None
        self._thread = None

    def __enter__(self):
        from app import create_app

        app = create_app({"TESTING": True, "APP_VERSION": "smoke-local"})
        self._srv = make_server(self.host, self.port, app)
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._srv:
            with contextlib.suppress(Exception):
                self._srv.shutdown()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


# ------------------------------- Test runner -------------------------------
@dataclass
class TestResult:
    name: str
    passed: bool
    details: str = ""
    duration_ms: int = 0


class SmokeTests:
    def __init__(self, base_url: str, timeout: float = 5.0, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = requests.Session()

    # Utilities
    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("verify", self.verify_ssl)
        return self.session.request(method, self._url(path), **kwargs)

    # Tests
    def test_health(self) -> TestResult:
        start = time.perf_counter()
        try:
            r = self._request("GET", "/health")
            ok = r.status_code == 200 and r.json().get("status") == "ok"
            details = f"status_code={r.status_code}, body={r.text[:200]}"
            return TestResult("health", ok, details, int((time.perf_counter() - start) * 1000))
        except Exception as e:
            return TestResult("health", False, f"exception: {e}", int((time.perf_counter() - start) * 1000))

    def test_version(self) -> TestResult:
        start = time.perf_counter()
        try:
            r = self._request("GET", "/api/version")
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            ver = data.get("version")
            ok = r.status_code == 200 and isinstance(ver, str) and len(ver) > 0
            details = f"status_code={r.status_code}, version={ver}"
            return TestResult("version", ok, details, int((time.perf_counter() - start) * 1000))
        except Exception as e:
            return TestResult("version", False, f"exception: {e}", int((time.perf_counter() - start) * 1000))

    def test_echo(self) -> TestResult:
        start = time.perf_counter()
        payload = {"message": "hello", "num": 42}
        try:
            r = self._request("POST", "/api/echo", json=payload)
            data = r.json()
            ok = r.status_code == 200 and data.get("echo") == payload
            details = f"status_code={r.status_code}, body={json.dumps(data)[:200]}"
            return TestResult("echo", ok, details, int((time.perf_counter() - start) * 1000))
        except Exception as e:
            return TestResult("echo", False, f"exception: {e}", int((time.perf_counter() - start) * 1000))

    def test_items_lifecycle(self) -> TestResult:
        start = time.perf_counter()
        try:
            # Create
            unique_name = f"smoke-item-{int(time.time())}"
            r_create = self._request("POST", "/api/items", json={"name": unique_name})
            ok_create = r_create.status_code in (200, 201)
            body_create = r_create.json() if ok_create else {}
            item_id = body_create.get("id")
            ok = ok_create and isinstance(item_id, str)
            # List and verify presence
            if ok:
                r_list = self._request("GET", "/api/items")
                ok_list = r_list.status_code == 200
                items = r_list.json().get("items", []) if ok_list else []
                present = any(i.get("id") == item_id and i.get("name") == unique_name for i in items)
                ok = ok_list and present
                details = f"created_id={item_id}, present={present}, total_items={len(items)}"
            else:
                details = f"create_failed: status_code={r_create.status_code}, body={r_create.text[:200]}"
            return TestResult("items_lifecycle", ok, details, int((time.perf_counter() - start) * 1000))
        except Exception as e:
            return TestResult("items_lifecycle", False, f"exception: {e}", int((time.perf_counter() - start) * 1000))

    def run_all(self) -> list[TestResult]:
        tests: list[Callable[[], TestResult]] = [
            self.test_health,
            self.test_version,
            self.test_echo,
            self.test_items_lifecycle,
        ]
        results: list[TestResult] = []
        for t in tests:
            results.append(t())
        return results


# ------------------------------- CLI / Driver -------------------------------

def wait_for(url: str, timeout: float = 10.0, verify_ssl: bool = True) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            r = requests.get(url, timeout=2.0, verify=verify_ssl)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def print_report(results: Iterable[TestResult]) -> None:
    total = 0
    passed = 0
    logging.info("\nSmoke test results:")
    for res in results:
        total += 1
        status = "PASS" if res.passed else "FAIL"
        if res.passed:
            passed += 1
        logging.info(f" - {res.name:18} {status:4}  ({res.duration_ms} ms)  {res.details}")
    logging.info(f"\nSummary: {passed}/{total} passed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run quick smoke tests locally or against a sandbox.")
    parser.add_argument("--mode", choices=["local", "remote"], default=os.getenv("SMOKE_MODE", "local"), help="local: spin up app; remote: use base URL")
    parser.add_argument("--base-url", default=os.getenv("SMOKE_BASE_URL"), help="Base URL for remote mode, e.g. https://sandbox.example.com")
    parser.add_argument("--port", type=int, default=int(os.getenv("SMOKE_PORT", "5001")), help="Port for local mode")
    parser.add_argument("--timeout", type=float, default=float(os.getenv("SMOKE_TIMEOUT", "5")), help="Per-request timeout in seconds")
    parser.add_argument("--wait", type=float, default=float(os.getenv("SMOKE_WAIT", "10")), help="Max seconds to wait for service to be ready")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification")
    parser.add_argument("--json", dest="json_out", action="store_true", help="Print JSON summary in addition to text output")

    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    verify_ssl = not args.insecure

    if args.mode == "remote":
        if not args.base_url:
            logging.error("Error: --base-url is required for remote mode")
            return 2
        base_url = args.base_url.rstrip("/")
        # Optionally wait for remote health if desired
        if not wait_for(base_url + "/health", timeout=args.wait, verify_ssl=verify_ssl):
            logging.error(f"Remote service at {base_url} not ready within {args.wait}s")
            return 1
        runner = SmokeTests(base_url, timeout=args.timeout, verify_ssl=verify_ssl)
        results = runner.run_all()
    else:
        # local mode
        with LocalServer(port=args.port) as srv:
            base_url = srv.base_url
            if not wait_for(base_url + "/health", timeout=args.wait, verify_ssl=False):
                logging.error(f"Local service at {base_url} not ready within {args.wait}s")
                return 1
            runner = SmokeTests(base_url, timeout=args.timeout, verify_ssl=False)
            results = runner.run_all()

    print_report(results)

    if args.json_out:
        summary = {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "details": r.details,
                    "duration_ms": r.duration_ms,
                }
                for r in results
            ],
        }
        print(json.dumps(summary, indent=2))

    all_passed = all(r.passed for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
