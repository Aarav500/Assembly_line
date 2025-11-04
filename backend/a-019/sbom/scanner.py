import os
import re
import json
import pathlib
import sys
from typing import Dict, List, Optional, Tuple

try:  # Python 3.8+
    import importlib.metadata as importlib_metadata
except Exception:  # pragma: no cover
    import importlib_metadata  # type: ignore

import requests

SPDX_HINTS = [
    (re.compile(r"apache( |-)?license( |v|version)?2(\.0)?", re.I), ("Apache-2.0", "Apache License 2.0")),
    (re.compile(r"mit( |-)license", re.I), ("MIT", "MIT License")),
    (re.compile(r"bsd( |-)3", re.I), ("BSD-3-Clause", "BSD 3-Clause")),
    (re.compile(r"bsd( |-)2", re.I), ("BSD-2-Clause", "BSD 2-Clause")),
    (re.compile(r"gpl( |-)v?3", re.I), ("GPL-3.0-only", "GNU General Public License v3.0")),
    (re.compile(r"gpl( |-)v?2", re.I), ("GPL-2.0-only", "GNU General Public License v2.0")),
    (re.compile(r"lgpl( |-)v?3", re.I), ("LGPL-3.0-only", "GNU Lesser General Public License v3.0")),
    (re.compile(r"lgpl( |-)v?2\.1", re.I), ("LGPL-2.1-only", "GNU Lesser General Public License v2.1")),
    (re.compile(r"mpl( |-)2(\.0)?", re.I), ("MPL-2.0", "Mozilla Public License 2.0")),
    (re.compile(r"apache.*1\.1", re.I), ("Apache-1.1", "Apache License 1.1")),
    (re.compile(r"isc", re.I), ("ISC", "ISC License")),
    (re.compile(r"agpl( |-)v?3", re.I), ("AGPL-3.0-only", "GNU Affero General Public License v3.0")),
]

LICENSE_FILE_REGEX = re.compile(r"(?i)(^|/)(LICENSE|LICENCE|COPYING|COPYRIGHT|NOTICE)(\..*)?$")


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirements_file(path: str) -> List[str]:
    names: List[str] = []
    if not os.path.isfile(path):
        return names
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("-r ") or line.startswith("--requirement"):
                parts = line.split()
                inc = parts[-1]
                inc_path = os.path.join(os.path.dirname(path), inc)
                names.extend(parse_requirements_file(inc_path))
                continue
            # Drop hashes and extras
            line = line.split(" ")[0]
            line = line.split(";")[0]
            # VCS/git: try to extract egg name
            if line.startswith(("git+", "hg+", "svn+", "bzr+")):
                m = re.search(r"[#&]egg=([A-Za-z0-9_.\-]+)", line)
                if m:
                    names.append(m.group(1))
                continue
            # direct URL with @ or name @ url
            if " @ " in line:
                nm = line.split(" @ ", 1)[0]
                names.append(nm)
                continue
            # split specifiers
            nm = re.split(r"==|>=|<=|~=|!=|>|<", line)[0]
            # remove extras: name[extra]
            nm = nm.split("[")[0]
            nm = nm.strip()
            if nm:
                names.append(nm)
    return names


def parse_pyproject(path: str) -> List[str]:
    # Minimal TOML parsing without dependency
    # We only look for [project] dependencies = [..] and [tool.poetry.dependencies]
    if not os.path.isfile(path):
        return []
    try:
        import tomllib  # Python 3.11+
    except Exception:
        try:
            import tomli as tomllib  # type: ignore
        except Exception:
            # Fallback: naive parse
            return _naive_parse_pyproject(path)

    with open(path, "rb") as f:
        data = tomllib.load(f)
    names: List[str] = []

    # PEP 621
    deps = (data.get("project") or {}).get("dependencies") or []
    for dep in deps:
        nm = str(dep).split(";")[0].split("[")[0]
        nm = re.split(r"==|>=|<=|~=|!=|>|<", nm)[0].strip()
        if nm:
            names.append(nm)

    # Poetry style
    poetry_deps = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
    for nm, spec in poetry_deps.items():
        if nm.lower() == "python":
            continue
        if isinstance(spec, dict):
            names.append(nm)
        else:
            names.append(nm)

    return names


def _naive_parse_pyproject(path: str) -> List[str]:
    names: List[str] = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            in_proj = False
            in_poetry = False
            for raw in f:
                line = raw.strip()
                if line.startswith("[") and line.endswith("]"):
                    sec = line.strip("[]").strip()
                    in_proj = sec == "project"
                    in_poetry = sec == "tool.poetry.dependencies"
                    continue
                if in_proj and line.startswith("dependencies") and "[" in line:
                    # collect array lines until closing ]
                    buf = line[line.find("[")+1:]
                    while "]" not in buf:
                        buf += f.readline()
                    arr = buf.split("]")[0]
                    for entry in arr.split(","):
                        nm = entry.strip().strip("'\"")
                        nm = nm.split(";")[0].split("[")[0]
                        nm = re.split(r"==|>=|<=|~=|!=|>|<", nm)[0].strip()
                        if nm:
                            names.append(nm)
                if in_poetry and "=" in line and not line.startswith("python"):
                    nm = line.split("=", 1)[0].strip()
                    nm = nm.split("[")[0].strip()
                    if nm:
                        names.append(nm)
    except Exception:
        pass
    return names


def _classifier_licenses(classifiers: List[str]) -> List[str]:
    out: List[str] = []
    for c in classifiers:
        if not c.lower().startswith("license ::"):
            continue
        parts = [p.strip() for p in c.split("::")]
        if parts:
            out.append(parts[-1])
    return out


def _guess_spdx_from_text(text: str) -> Optional[Tuple[str, str]]:
    t = text or ""
    for rx, pair in SPDX_HINTS:
        if rx.search(t):
            return pair
    return None


def _read_license_text(dist) -> Optional[str]:
    files = getattr(dist, "files", None)
    if not files:
        return None
    for f in files:
        p = dist.locate_file(f)
        try:
            if LICENSE_FILE_REGEX.search(str(p)) and p.is_file():
                return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
    return None


def _purl(name: str, version: Optional[str]) -> str:
    n = normalize_name(name)
    if version:
        return f"pkg:pypi/{n}@{version}"
    return f"pkg:pypi/{n}"


def _from_metadata(dist) -> Dict:
    meta = dist.metadata
    name = meta.get("Name") or dist.metadata['Name'] if 'Name' in dist.metadata else dist.metadata.get('name', '')
    version = meta.get("Version")
    summary = meta.get("Summary")
    home = meta.get("Home-page") or meta.get("Home-Page") or meta.get("Project-URL")
    author = meta.get("Author") or meta.get("Author-email")
    lic = meta.get("License")
    classifiers = meta.get_all("Classifier") or []

    license_from = "metadata-field" if lic else None
    license_name = lic.strip() if lic else None
    license_id = None

    # If classifier has a specific license, prefer it
    cl_licenses = _classifier_licenses(classifiers)
    if cl_licenses:
        license_from = "classifier"
        license_name = cl_licenses[-1]

    license_text = _read_license_text(dist)

    # Try map to SPDX id from license_name or license_text
    pair = None
    if license_name:
        pair = _guess_spdx_from_text(license_name)
    if not pair and license_text:
        pair = _guess_spdx_from_text(license_text[:4000])
    if pair:
        license_id, license_name2 = pair
        # Preserve original name but set id
        if not license_name:
            license_name = license_name2

    return {
        "name": name,
        "version": version,
        "summary": summary,
        "home_page": home,
        "author": author,
        "purl": _purl(name, version),
        "license": {
            "id": license_id,
            "name": license_name,
            "source": license_from,
        } if (license_id or license_name) else None,
    }


def scan_environment() -> List[Dict]:
    """Scan installed packages in current environment."""
    packages = []
    try:
        for dist in importlib_metadata.distributions():
            try:
                pkg = _from_metadata(dist)
                packages.append(pkg)
            except Exception:
                continue
    except Exception:
        pass
    return packages


def scan_requirements(path: str) -> List[Dict]:
    """Scan packages from requirements.txt file."""
    names = parse_requirements_file(path)
    packages = []
    for name in names:
        try:
            dist = importlib_metadata.distribution(name)
            pkg = _from_metadata(dist)
            packages.append(pkg)
        except Exception:
            # Package not installed, add minimal info
            packages.append({
                "name": name,
                "version": None,
                "summary": None,
                "home_page": None,
                "author": None,
                "purl": _purl(name, None),
                "license": None,
            })
    return packages


def scan_pyproject(path: str) -> List[Dict]:
    """Scan packages from pyproject.toml file."""
    names = parse_pyproject(path)
    packages = []
    for name in names:
        try:
            dist = importlib_metadata.distribution(name)
            pkg = _from_metadata(dist)
            packages.append(pkg)
        except Exception:
            # Package not installed, add minimal info
            packages.append({
                "name": name,
                "version": None,
                "summary": None,
                "home_page": None,
                "author": None,
                "purl": _purl(name, None),
                "license": None,
            })
    return packages
