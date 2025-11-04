import os
import json
from datetime import datetime
from flask import current_app

from .utils import (
    ensure_dir,
    run_subprocess,
    write_json,
    reports_subdir,
)
from load_tests.load_test import run_load_test


def timestamp(tz):
    return datetime.now(tz).strftime("%Y%m%d_%H%M%S")


def integration_tests_job(app):
    with app.app_context():
        tz = current_app.config["TIMEZONE"]
        ts = timestamp(tz)
        reports_dir = current_app.config["REPORTS_DIR"]
        out_dir = reports_subdir(reports_dir, "integration")
        junit_path = os.path.join(out_dir, f"junit-{ts}.xml")
        log_path = os.path.join(out_dir, f"pytest-{ts}.log")
        summary_path = os.path.join(out_dir, f"summary-{ts}.json")

        cmd = [
            os.environ.get("PYTHON", os.sys.executable),
            "-m",
            "pytest",
            "-q",
            "tests/integration",
            f"--junitxml={junit_path}",
        ]

        current_app.logger.info("Starting integration tests: %s", " ".join(cmd))
        result = run_subprocess(cmd)
        current_app.logger.info("Integration tests finished with code %s", result["returncode"])

        # Write raw output log
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(result["stdout"])  # includes both stdout+stderr captured

        summary = {
            "type": "integration",
            "timestamp": ts,
            "returncode": result["returncode"],
            "passed": result["returncode"] == 0,
            "junit_report": os.path.abspath(junit_path),
            "log": os.path.abspath(log_path),
            "started": result["started"],
            "ended": result["ended"],
            "duration_seconds": result["duration_seconds"],
        }
        write_json(summary_path, summary)
        current_app.logger.info("Integration test summary written: %s", summary_path)
        return summary


def load_tests_job(app):
    with app.app_context():
        tz = current_app.config["TIMEZONE"]
        ts = timestamp(tz)
        reports_dir = current_app.config["REPORTS_DIR"]
        out_dir = reports_subdir(reports_dir, "load")
        result_path = os.path.join(out_dir, f"result-{ts}.json")

        url = current_app.config["LOADTEST_URL"]
        duration = current_app.config["LOADTEST_DURATION"]
        concurrency = current_app.config["LOADTEST_CONCURRENCY"]
        rps = current_app.config["LOADTEST_RPS"]
        timeout = current_app.config["LOADTEST_TIMEOUT"]

        current_app.logger.info(
            "Starting load test url=%s duration=%ss concurrency=%s rps=%s timeout=%ss",
            url,
            duration,
            concurrency,
            rps,
            timeout,
        )
        result = run_load_test(
            url=url,
            duration_seconds=duration,
            concurrency=concurrency,
            target_rps=rps,
            timeout=timeout,
            tz=tz,
        )
        write_json(result_path, result)
        current_app.logger.info("Load test results written: %s", result_path)
        return result

