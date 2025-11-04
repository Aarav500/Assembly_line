from typing import Any, Dict, List


def safe_bool(val, default=False):
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in ("1", "true", "yes", "y", "on")


def normalize_trivy(trivy_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    # Trivy FS/Image scans can return either an object with Results (new) or array (older). Normalize to results.
    results = []
    if isinstance(trivy_json, dict) and "Results" in trivy_json:
        results = trivy_json.get("Results") or []
    elif isinstance(trivy_json, list):
        # Some versions return an array of report objects per target
        for item in trivy_json:
            results.extend(item.get("Results") or [])

    for res in results:
        res_type = res.get("Type") or res.get("Class") or "unknown"
        target = res.get("Target")

        # Vulnerabilities
        for v in res.get("Vulnerabilities") or []:
            findings.append({
                "source": "trivy",
                "target": target,
                "type": res_type,
                "category": "vulnerability",
                "id": v.get("VulnerabilityID") or v.get("VulnID"),
                "title": v.get("Title"),
                "severity": v.get("Severity"),
                "pkgName": v.get("PkgName"),
                "pkgType": v.get("PkgType") or res_type,
                "installedVersion": v.get("InstalledVersion"),
                "fixedVersion": v.get("FixedVersion"),
                "description": v.get("Description"),
                "references": v.get("References") or [],
                "cvss": v.get("CVSS"),
                "dataSource": v.get("DataSource"),
            })

        # Misconfigurations (from config scan)
        for m in res.get("Misconfigurations") or []:
            findings.append({
                "source": "trivy",
                "target": target,
                "type": res_type,
                "category": "misconfiguration",
                "id": m.get("ID"),
                "title": m.get("Title"),
                "severity": m.get("Severity"),
                "pkgName": None,
                "pkgType": res_type,
                "installedVersion": None,
                "fixedVersion": None,
                "description": m.get("Description"),
                "references": m.get("References") or [],
                "cvss": None,
                "dataSource": None,
            })

    return findings


def normalize_snyk(snyk_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    # Snyk has different schemas for OS/Code/Container scans.
    # Common field: vulnerabilities array (legacy) or issues.vulnerabilities (newer).
    vulns = []
    if isinstance(snyk_json, dict):
        if "vulnerabilities" in snyk_json and isinstance(snyk_json.get("vulnerabilities"), list):
            vulns = snyk_json.get("vulnerabilities") or []
        elif "issues" in snyk_json and isinstance(snyk_json.get("issues"), dict):
            vulns = (snyk_json["issues"].get("vulnerabilities") or [])

    for v in vulns:
        pkg_name = v.get("package") or v.get("packageName") or v.get("from")[0] if v.get("from") else None
        findings.append({
            "source": "snyk",
            "target": snyk_json.get("displayTargetFile") or snyk_json.get("path") or snyk_json.get("docker") or snyk_json.get("projectName"),
            "type": v.get("packageManager") or v.get("ecosystem") or "unknown",
            "category": "vulnerability",
            "id": v.get("id") or v.get("identifiers", {}).get("CVE", [None])[0],
            "title": v.get("title") or v.get("id"),
            "severity": (v.get("severity") or "").upper(),
            "pkgName": pkg_name,
            "pkgType": v.get("packageManager") or v.get("ecosystem") or "unknown",
            "installedVersion": v.get("version") or v.get("fromVersion") or v.get("nameAndVersion"),
            "fixedVersion": (v.get("fixedIn") or [None])[0] if isinstance(v.get("fixedIn"), list) else v.get("fixedIn"),
            "description": v.get("description") or v.get("title"),
            "references": v.get("references") or v.get("urls") or [],
            "cvss": v.get("cvssScore") or v.get("cvssDetails"),
            "dataSource": "snyk",
        })

    return findings

