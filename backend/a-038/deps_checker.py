import re
import time
from typing import List, Dict, Tuple

import requests
from packaging.version import Version, InvalidVersion


REQ_LINE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*([=<>!~]=)\s*([^#;\s]+)")
COMMENT = re.compile(r"^\s*#")


def parse_requirements_text(text: str) -> List[Dict[str, str]]:
    packages = []
    if not text:
        return packages
    for line in text.splitlines():
        if not line or COMMENT.match(line):
            continue
        m = REQ_LINE.match(line)
        if not m:
            continue
        name, op, ver = m.group(1), m.group(2), m.group(3)
        if op == "==":
            packages.append({"name": name.strip(), "version": ver.strip()})
    return packages


def _normalize_name(name: str) -> str:
    return name.replace("_", "-").lower()


def fetch_latest_versions(packages: List[Dict[str, str]], timeout: float = 5.0) -> Tuple[Dict[str, str], Dict[str, str]]:
    latest_map: Dict[str, str] = {}
    errors: Dict[str, str] = {}

    session = requests.Session()
    session.headers.update({"User-Agent": "risk-scoring/1.0"})

    for p in packages:
        name = p.get("name")
        if not name:
            continue
        key = _normalize_name(name)
        if key in latest_map or key in errors:
            continue
        url = f"https://pypi.org/pypi/{key}/json"
        try:
            resp = session.get(url, timeout=timeout)
            if resp.status_code != 200:
                errors[key] = f"HTTP {resp.status_code}"
                continue
            data = resp.json()
            releases = data.get("releases") or {}
            versions = []
            for ver_str, files in releases.items():
                if not files:
                    continue
                try:
                    v = Version(ver_str)
                except InvalidVersion:
                    continue
                # Skip pre-releases
                if v.is_prerelease:
                    continue
                versions.append(v)
            if not versions:
                errors[key] = "no stable releases"
                continue
            latest = str(sorted(versions)[-1])
            latest_map[key] = latest
            # be polite but minimal
            time.sleep(0.05)
        except requests.RequestException as e:
            errors[key] = str(e)
        except Exception as e:
            errors[key] = f"unexpected: {e}"
    return latest_map, errors


def _release_diff(current: Version, latest: Version) -> str:
    # Compare first three release components (major, minor, micro)
    c = list(current.release) + [0, 0, 0]
    l = list(latest.release) + [0, 0, 0]
    c = c[:3]
    l = l[:3]
    if l[0] > c[0]:
        return "major"
    if l[1] > c[1]:
        return "minor"
    if l[2] > c[2]:
        return "patch"
    return "none"


def analyze_outdated(packages: List[Dict[str, str]], latest_map: Dict[str, str]) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for p in packages:
        name = p.get("name")
        version = p.get("version")
        norm = _normalize_name(name)
        latest_str = latest_map.get(norm)

        current_v = None
        latest_v = None
        try:
            if version:
                current_v = Version(str(version))
        except InvalidVersion:
            pass
        try:
            if latest_str:
                latest_v = Version(str(latest_str))
        except InvalidVersion:
            pass

        is_outdated = False
        severity = None
        if current_v and latest_v:
            is_outdated = latest_v > current_v
            severity = _release_diff(current_v, latest_v) if is_outdated else "none"

        results.append({
            "name": name,
            "current_version": version,
            "latest_version": latest_str,
            "is_outdated": bool(is_outdated),
            "severity": severity if severity else (None if latest_str else None),
        })
    return results

