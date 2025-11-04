import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


DEFAULT_POLICY = {
    "allow": [
        "MIT",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "BSD",
        "Apache-2.0",
        "ISC",
        "MPL-2.0",
        "Python-2.0",
    ],
    "deny": [
        "GPL-2.0",
        "GPL-3.0",
        "AGPL-3.0",
        "LGPL-3.0",
        "SSPL-1.0",
    ],
    "ignore_packages": [
        "pip",
        "setuptools",
        "wheel",
        "pip-licenses",
        "cyclonedx-bom",
    ],
    "fail_on_unknown": True,
    "save_json_report": "build/licenses/report.json",
    "save_attribution": "build/licenses/THIRD_PARTY_NOTICES.txt",
}

NORMALIZE_MAP = {
    "apache software license": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache-2": "Apache-2.0",
    "bsd license": "BSD",
    "bsd-3-clause": "BSD-3-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "bsd 2-clause": "BSD-2-Clause",
    "mit license": "MIT",
    "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "mpl 2.0": "MPL-2.0",
    "isc license": "ISC",
    "gnu general public license v3 (gplv3)": "GPL-3.0",
    "gnu lesser general public license v3 (lgplv3)": "LGPL-3.0",
    "gnu affero general public license v3": "AGPL-3.0",
    "python software foundation license": "Python-2.0",
}

SPLIT_TOKENS = re.compile(r"\s*(?:\bor\b|\band\b|/|,|;|\||\\)\s*", re.IGNORECASE)


def load_policy(path: Path) -> Dict:
    if path.exists():
        with path.open() as f:
            return json.load(f)
    return DEFAULT_POLICY


def ensure_dirs(policy: Dict):
    Path(policy["save_json_report"]).parent.mkdir(parents=True, exist_ok=True)
    Path(policy["save_attribution"]).parent.mkdir(parents=True, exist_ok=True)


def run_pip_licenses(ignore: List[str]) -> List[Dict]:
    cmd = [
        "pip-licenses",
        "--format=json",
        "--with-urls",
        "--with-authors",
        "--with-license-file",
    ]
    if ignore:
        cmd += ["--ignore-packages", *ignore]
    print(f"[license_check] Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        raise SystemExit(res.returncode)
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError:
        # Some versions write JSON to stderr when using --with-license-file. Try stderr.
        try:
            data = json.loads(res.stderr)
        except Exception as e:
            print("Failed to parse pip-licenses output as JSON")
            print("STDOUT:\n", res.stdout)
            print("STDERR:\n", res.stderr)
            raise e
    return data


def normalize_license_name(name: str) -> str:
    if not name:
        return "UNKNOWN"
    s = name.strip().lower()
    s = s.replace("license", "").strip()
    s = re.sub(r"\s+", " ", s)
    if s in NORMALIZE_MAP:
        return NORMALIZE_MAP[s]
    # Simple heuristics
    patterns = [
        (r"apache.*2", "Apache-2.0"),
        (r"bsd.*3", "BSD-3-Clause"),
        (r"bsd.*2", "BSD-2-Clause"),
        (r"\bbsd\b", "BSD"),
        (r"\bmit\b", "MIT"),
        (r"mpl.*2", "MPL-2.0"),
        (r"\bisc\b", "ISC"),
        (r"agpl.*3", "AGPL-3.0"),
        (r"gpl.*3", "GPL-3.0"),
        (r"lgpl.*3", "LGPL-3.0"),
        (r"python software", "Python-2.0"),
    ]
    for rx, value in patterns:
        if re.search(rx, s):
            return value
    return name.strip()


def split_licenses(expr: str) -> List[str]:
    if not expr:
        return ["UNKNOWN"]
    parts = [p for p in SPLIT_TOKENS.split(expr) if p]
    if not parts:
        parts = [expr]
    return [normalize_license_name(p) for p in parts]


def match_any(name: str, patterns: List[str]) -> bool:
    n = name.lower()
    for p in patterns:
        pl = p.lower()
        if pl == n or pl in n or n in pl:
            return True
    return False


def evaluate_license(expr: str, allow: List[str], deny: List[str], fail_on_unknown: bool) -> Tuple[str, str]:
    tokens = split_licenses(expr)
    # If any token is explicitly denied, it's a violation
    for t in tokens:
        if match_any(t, deny):
            return ("denied", t)
    # If any token is explicitly allowed, consider it allowed
    for t in tokens:
        if match_any(t, allow):
            return ("allowed", t)
    # Unknown
    if fail_on_unknown:
        return ("unknown", ", ".join(tokens))
    return ("allowed", tokens[0] if tokens else "UNKNOWN")


def write_reports(policy: Dict, packages: List[Dict], violations: List[Dict]):
    report = {
        "summary": {
            "total_packages": len(packages),
            "violations": len(violations),
        },
        "violations": violations,
        "packages": packages,
    }
    with open(policy["save_json_report"], "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Attribution file
    lines = []
    lines.append("THIRD-PARTY NOTICES\n")
    lines.append("This file lists third-party packages and their licenses.\n\n")
    for p in packages:
        name = p.get("Name")
        version = p.get("Version")
        license_name = p.get("License")
        url = p.get("URL") or ""
        lines.append(f"- {name} {version} | License: {license_name} | {url}\n")
        text = p.get("LicenseText") or p.get("LicenseFile")
        if text:
            lines.append("\n")
            # If a path is provided instead of text, attempt to read it
            if isinstance(text, str) and len(text) < 4096 and os.path.exists(text):
                try:
                    with open(text, "r", encoding="utf-8", errors="ignore") as lf:
                        license_text = lf.read()
                except Exception:
                    license_text = "(License text not available)"
            else:
                license_text = text if isinstance(text, str) else json.dumps(text)
            lines.append(license_text)
            lines.append("\n\n")

    with open(policy["save_attribution"], "w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    policy_path = Path(os.getenv("LICENSE_POLICY", "policy/license-policy.json"))
    policy = load_policy(policy_path)
    ensure_dirs(policy)

    ignore = policy.get("ignore_packages", [])
    data = run_pip_licenses(ignore)

    allow = policy.get("allow", [])
    deny = policy.get("deny", [])
    fail_on_unknown = bool(policy.get("fail_on_unknown", True))

    enriched = []
    violations = []

    for item in data:
        name = item.get("Name")
        version = item.get("Version")
        license_expr = item.get("License") or "UNKNOWN"
        status, matched = evaluate_license(license_expr, allow, deny, fail_on_unknown)

        rec = dict(item)
        rec["_policy_status"] = status
        rec["_policy_matched"] = matched
        enriched.append(rec)

        if status in {"denied", "unknown"}:
            violations.append({
                "name": name,
                "version": version,
                "license": license_expr,
                "matched": matched,
                "status": status,
            })

    write_reports(policy, enriched, violations)

    if violations:
        print("[license_check] License policy violations detected:\n")
        for v in violations:
            print(f"- {v['name']} {v['version']}: {v['license']} -> {v['status']} (matched: {v['matched']})")
        print(f"\nSee report: {policy['save_json_report']}")
        raise SystemExit(1)

    print("[license_check] License check passed.")


if __name__ == "__main__":
    main()

