import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from packaging.version import Version, InvalidVersion


DEPENDENCY_FILE_PATTERNS = (
    re.compile(r"(^|/)requirements(\..+)?\.txt$"),
    re.compile(r"(^|/)Pipfile$"),
    re.compile(r"(^|/)pyproject\.toml$"),
    re.compile(r"(^|/)setup\.cfg$"),
    re.compile(r"(^|/)package\.json$"),
    re.compile(r"(^|/)package-lock\.json$"),
    re.compile(r"(^|/)poetry\.lock$"),
)


@dataclass
class DepChange:
    name: str
    old_version: Optional[str]
    new_version: Optional[str]
    change_type: str  # major/minor/patch/unknown


def is_dependency_file(filename: str) -> bool:
    return any(p.search(filename) for p in DEPENDENCY_FILE_PATTERNS)


def parse_requirements_line(line: str) -> Optional[Tuple[str, str]]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    # simplest: package==1.2.3
    m = re.match(r"([A-Za-z0-9_.\-]+)\s*==\s*([A-Za-z0-9_.\-]+)$", line)
    if m:
        return m.group(1).lower(), m.group(2)
    # allow >= or <= or ~=
    m2 = re.match(r"([A-Za-z0-9_.\-]+)\s*[><=~!]{1,2}\s*([A-Za-z0-9_.\-]+)$", line)
    if m2:
        return m2.group(1).lower(), m2.group(2)
    return None


def parse_json_dep_line(line: str) -> Optional[Tuple[str, str]]:
    # lines like: +    "requests": "^2.31.0",
    m = re.match(r"[+\-]\s*\"([^\"]+)\"\s*:\s*\"([^\"]+)\"", line.strip())
    if m:
        name = m.group(1)
        version = m.group(2)
        return name, version.lstrip("v")
    return None


def parse_patch_for_file(filename: str, patch: Optional[str]) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    if not patch:
        return {}
    removed: Dict[str, str] = {}
    added: Dict[str, str] = {}
    for raw in patch.splitlines():
        if raw.startswith("---") or raw.startswith("+++") or raw.startswith("@@"):
            continue
        if not raw or raw[0] not in "+-":
            continue
        line = raw[1:]
        parsed = None
        if filename.endswith(".txt") or filename.endswith("Pipfile") or filename.endswith("poetry.lock") or filename.endswith("pyproject.toml") or filename.endswith("setup.cfg"):
            parsed = parse_requirements_line(line)
        elif filename.endswith("package.json") or filename.endswith("package-lock.json"):
            parsed = parse_json_dep_line(raw)  # keep +/- prefix for JSON helper
        if not parsed:
            continue
        name, ver = parsed
        if raw.startswith("-"):
            removed[name] = ver
        elif raw.startswith("+"):
            added[name] = ver
    result: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    keys = set(removed.keys()) | set(added.keys())
    for k in keys:
        old_v = removed.get(k)
        new_v = added.get(k)
        # Only keep if version changed
        if old_v != new_v:
            result[k] = (old_v, new_v)
    return result


def detect_from_title_or_body(title: str, body: str) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    # Dependabot pattern: Bumps requests from 2.25.0 to 2.31.0.
    pat = re.compile(r"Bumps\s+([A-Za-z0-9_.\-/]+)\s+from\s+([0-9A-Za-z_.\-]+)\s+to\s+([0-9A-Za-z_.\-]+)", re.IGNORECASE)
    found: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    for m in pat.finditer(title + "\n" + (body or "")):
        name = m.group(1).split("/")[-1].lower()
        found[name] = (m.group(2), m.group(3))
    # Renovate pattern: chore(deps): update dependency requests to v2.31.0
    pat2 = re.compile(r"update\s+dependency\s+([A-Za-z0-9_.\-]+)/?([A-Za-z0-9_.\-]*)\s+to\s+v?([0-9A-Za-z_.\-]+)", re.IGNORECASE)
    for m in pat2.finditer(title + "\n" + (body or "")):
        name = (m.group(1) if m.group(2) == "" else m.group(2)).lower() or m.group(1).lower()
        found.setdefault(name, (None, m.group(3)))
    return found


def semver_change_type(old: Optional[str], new: Optional[str]) -> str:
    if not old or not new:
        return "unknown"
    try:
        v_old = Version(str(old).lstrip("v"))
        v_new = Version(str(new).lstrip("v"))
    except InvalidVersion:
        return "unknown"
    if v_new.release and v_old.release:
        major_old = v_old.release[0] if len(v_old.release) > 0 else 0
        major_new = v_new.release[0] if len(v_new.release) > 0 else 0
        minor_old = v_old.release[1] if len(v_old.release) > 1 else 0
        minor_new = v_new.release[1] if len(v_new.release) > 1 else 0
        micro_old = v_old.release[2] if len(v_old.release) > 2 else 0
        micro_new = v_new.release[2] if len(v_new.release) > 2 else 0
        if major_new > major_old:
            return "major"
        if minor_new > minor_old:
            return "minor"
        if micro_new > micro_old:
            return "patch"
    return "unknown"


def analyze_pr_changes(files: List[Dict[str, Any]], title: str, body: str) -> Dict[str, Any]:
    changes: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    for f in files:
        filename = f.get("filename")
        if not filename or not is_dependency_file(filename):
            continue
        patch = f.get("patch")
        file_changes = parse_patch_for_file(filename, patch)
        for name, (old_v, new_v) in file_changes.items():
            changes[name.lower()] = (old_v, new_v)

    # Fallback detection from title/body
    if not changes:
        t_changes = detect_from_title_or_body(title or "", body or "")
        for k, v in t_changes.items():
            if k not in changes:
                changes[k] = v

    dependencies: List[DepChange] = []
    for name, (old_v, new_v) in changes.items():
        change_type = semver_change_type(old_v, new_v)
        dependencies.append(DepChange(name=name, old_version=old_v, new_version=new_v, change_type=change_type))

    return {"dependencies": dependencies, "title": title, "body": body}


def overall_risk_level(analysis: Dict[str, Any], config=None) -> str:
    deps: List[DepChange] = analysis.get("dependencies", [])
    if not deps:
        return "unknown"
    # Defaults if no config
    high_many = getattr(config, "high_risk_if_many", 15) if config else 15
    med_many = getattr(config, "medium_risk_if_many", 7) if config else 7
    sensitive = set(getattr(config, "sensitive_packages", [])) if config else set()

    # Count types
    majors = sum(1 for d in deps if d.change_type == "major")
    minors = sum(1 for d in deps if d.change_type == "minor")
    patches = sum(1 for d in deps if d.change_type == "patch")

    if len(deps) >= high_many:
        return "high"
    if len(deps) >= med_many:
        # Escalate to medium at least
        level = "medium"
    else:
        level = "low"

    if majors > 0:
        return "high"
    if minors > 3:
        return "medium"

    # Sensitive packages bump escalation
    for d in deps:
        if d.name.lower() in sensitive and d.change_type in ("major", "minor"):
            return "high"

    if patches > 0 and level == "low":
        return "low"
    return level


def build_risk_comment(analysis: Dict[str, Any], risk: str, marker: str, config) -> str:
    deps: List[DepChange] = analysis.get("dependencies", [])
    lines: List[str] = []
    lines.append(marker)
    lines.append(f"Automated dependency risk assessment: {risk.upper()}")
    lines.append("")
    lines.append("Summary of changes:")

    shown = 0
    max_show = getattr(config, "max_dependencies_in_comment", 50)
    for d in deps:
        if shown >= max_show:
            break
        lines.append(f"- {d.name}: {d.old_version or '?'} -> {d.new_version or '?'} ({d.change_type})")
        shown += 1
    if len(deps) > shown:
        lines.append(f"... and {len(deps) - shown} more dependency updates")

    lines.append("")
    lines.append("Heuristics applied:")
    lines.append("- Major version bumps are HIGH risk")
    lines.append("- Multiple minor bumps may be MEDIUM risk")
    lines.append("- Patch bumps are typically LOW risk")
    lines.append("- Critical framework/runtime libraries are considered sensitive")

    lines.append("")
    if getattr(config, "auto_merge", False):
        allowed = ", ".join(getattr(config, "auto_merge_risk_levels", ["low"]))
        lines.append(f"Auto-merge is enabled for risk: {allowed}")
    else:
        lines.append("Auto-merge is disabled for this repository")

    return "\n".join(lines)

