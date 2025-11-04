import sys
import os
import json
import shutil
import subprocess
from datetime import datetime
from typing import Dict, Any, List


def _safe_json_loads(s: str):
    try:
        return json.loads(s)
    except Exception:
        return None


def _severity_of(vuln: Dict[str, Any]) -> str:
    # Try common fields from pip-audit's JSON and OSV forms
    # Priority: explicit severity string, highest CVSS score mapping, else UNKNOWN
    # pip-audit OSV advisory may include 'severity': [{'type':'CVSS_V3','score':'7.5'}]
    sev = vuln.get("severity")
    if isinstance(sev, str) and sev:
        return sev.upper()
    # nested advisory
    advisory = vuln.get("advisory") or {}
    sev2 = advisory.get("severity")
    if isinstance(sev2, str) and sev2:
        return sev2.upper()
    sev_list = advisory.get("severities") or advisory.get("severity") or vuln.get("severities")
    scores = []
    if isinstance(sev_list, list):
        for entry in sev_list:
            score = entry.get("score") or entry.get("cvss_score")
            try:
                if score is not None:
                    scores.append(float(score))
            except Exception:
                pass
    if scores:
        s = max(scores)
        if s >= 9.0:
            return "CRITICAL"
        if s >= 7.0:
            return "HIGH"
        if s >= 4.0:
            return "MEDIUM"
        return "LOW"
    return "UNKNOWN"


def run_pip_audit(requirements_file: str = None, timeout: int = 180) -> Dict[str, Any]:
    cmd = [sys.executable, "-m", "pip_audit", "-f", "json", "--progress-spinner", "off"]
    if requirements_file and os.path.exists(requirements_file):
        cmd.extend(["-r", requirements_file])
    # else scan current environment
    try:
        p = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
        )
    except FileNotFoundError:
        return {"ok": False, "error": "pip-audit not installed", "results": []}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "pip-audit timed out", "results": []}

    data = _safe_json_loads(p.stdout.strip())
    if data is None:
        return {"ok": False, "error": (p.stderr or "pip-audit returned non-JSON output"), "results": []}

    # data expected as list of package results
    results = []
    if isinstance(data, list):
        for pkg in data:
            name = pkg.get("name")
            version = pkg.get("version")
            vulns = pkg.get("vulns") or pkg.get("vulnerabilities") or []
            normalized_vulns = []
            for v in vulns:
                normalized_vulns.append({
                    "id": v.get("id") or v.get("vuln_id") or (v.get("advisory") or {}).get("id"),
                    "aliases": v.get("aliases") or (v.get("advisory") or {}).get("aliases") or [],
                    "fix_versions": v.get("fix_versions") or (v.get("advisory") or {}).get("fixed_versions") or [],
                    "description": v.get("description") or (v.get("advisory") or {}).get("summary") or "",
                    "severity": _severity_of(v),
                    "url": (v.get("advisory") or {}).get("url") or (v.get("references") or [None])[0],
                })
            results.append({"name": name, "version": version, "vulns": normalized_vulns})
    return {"ok": True, "results": results}


def get_outdated_packages(timeout: int = 60) -> Dict[str, Any]:
    cmd = [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"]
    try:
        p = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "pip list timed out", "results": []}

    data = _safe_json_loads(p.stdout.strip())
    if data is None:
        return {"ok": False, "error": (p.stderr or "pip list returned non-JSON output"), "results": []}

    results = []
    if isinstance(data, list):
        for d in data:
            results.append({
                "name": d.get("name"),
                "current": d.get("version"),
                "latest": d.get("latest_version") or d.get("latest"),
                "latest_filetype": d.get("latest_filetype"),
            })
    return {"ok": True, "results": results}


def _summarize(vuln_results: List[Dict[str, Any]]):
    severity_buckets = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
    total_vulns = 0
    affected_packages = 0
    for pkg in vuln_results:
        vulns = pkg.get("vulns", [])
        if vulns:
            affected_packages += 1
        for v in vulns:
            total_vulns += 1
            sev = (v.get("severity") or "UNKNOWN").upper()
            sev = sev if sev in severity_buckets else "UNKNOWN"
            severity_buckets[sev] += 1
    return {
        "affected_packages": affected_packages,
        "total_vulnerabilities": total_vulns,
        "by_severity": severity_buckets,
    }


def build_digest(config) -> Dict[str, Any]:
    req_file = config.get("REQUIREMENTS_FILE", "requirements.txt")
    pip_audit = run_pip_audit(req_file if os.path.exists(req_file) else None, timeout=config.get("PIP_AUDIT_TIMEOUT", 180))
    outdated = get_outdated_packages(timeout=config.get("PIP_OUTDATED_TIMEOUT", 60))

    vuln_results = pip_audit.get("results", [])
    outdated_results = outdated.get("results", [])

    # Sorts
    def severity_rank(s):
        order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}
        return order.get(s.upper(), 0)

    top_vuln_packages = []
    for pkg in vuln_results:
        pkg_copy = dict(pkg)
        pkg_copy["vulns"] = sorted(pkg.get("vulns", []), key=lambda x: severity_rank(x.get("severity", "UNKNOWN")), reverse=True)
        if pkg_copy["vulns"]:
            top_vuln_packages.append(pkg_copy)

    top_vuln_packages = sorted(top_vuln_packages, key=lambda p: severity_rank(p["vulns"][0].get("severity", "UNKNOWN")), reverse=True)

    summary = _summarize(vuln_results)

    # Limit size for email readability
    max_v = int(config.get("MAX_VULN_ITEMS", 200))
    max_o = int(config.get("MAX_OUTDATED_ITEMS", 200))

    generated_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    return {
        "generated_at": generated_at,
        "app_name": config.get("APP_NAME", "Flask App"),
        "audit_ok": pip_audit.get("ok", False),
        "audit_error": None if pip_audit.get("ok") else pip_audit.get("error"),
        "outdated_ok": outdated.get("ok", False),
        "outdated_error": None if outdated.get("ok") else outdated.get("error"),
        "summary": summary,
        "vulnerable_packages": top_vuln_packages[:max_v],
        "outdated_packages": sorted(outdated_results, key=lambda x: x.get("name", "").lower())[:max_o],
    }

