import datetime as _dt
from typing import Any, Dict, List, Optional

from compliance.checks.gdpr import gdpr_checks
from compliance.checks.hipaa import hipaa_checks


def _severity_rank(sev: str) -> int:
    order = {"none": -1, "low": 0, "medium": 1, "high": 2}
    return order.get(str(sev).lower(), 1)


def run_checks(config: Dict[str, Any], only: Optional[str] = None, fail_on: Optional[str] = None) -> Dict[str, Any]:
    fail_on = (fail_on or "medium").lower()

    # Collect checks
    checks = []
    if only is None:
        checks.extend(gdpr_checks())
        checks.extend(hipaa_checks())
    elif only.lower() == "gdpr":
        checks.extend(gdpr_checks())
    elif only.lower() == "hipaa":
        checks.extend(hipaa_checks())
    else:
        raise ValueError("Invalid 'only' filter. Use gdpr or hipaa")

    results: List[Dict[str, Any]] = []

    for chk in checks:
        try:
            r = chk(config)
        except Exception as e:
            # Hard failure of check -> mark fail, high severity diagnostic
            r = {
                "id": getattr(chk, "id", chk.__name__),
                "title": getattr(chk, "title", "Check Execution Error"),
                "category": getattr(chk, "category", "general"),
                "severity": "high",
                "status": "fail",
                "applicable": True,
                "message": f"Check raised exception: {e}",
                "remediation": "Fix configuration or check implementation.",
                "references": [],
            }
        results.append(r)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.get("status") == "pass")
    failed = sum(1 for r in results if r.get("status") == "fail")
    skipped = sum(1 for r in results if r.get("status") == "skipped")

    # Determine exit code
    threshold = _severity_rank(fail_on)
    exit_code = 0
    for r in results:
        if r.get("status") == "fail" and _severity_rank(r.get("severity", "medium")) >= threshold and threshold >= 0:
            exit_code = 1
            break

    report = {
        "generated_at": _dt.datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "fail_on": fail_on,
        },
        "results": results,
        "exit_code": exit_code,
    }

    return report

