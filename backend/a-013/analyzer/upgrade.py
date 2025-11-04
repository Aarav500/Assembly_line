from __future__ import annotations
from typing import Dict, List, Optional, Any, Tuple
from packaging.version import Version, InvalidVersion
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

from .pypi_client import PyPIClient
from .compat import is_python_compatible, framework_warnings_for_release


def _version_or_none(s: Optional[str]) -> Optional[Version]:
    if not s:
        return None
    try:
        return Version(str(s))
    except InvalidVersion:
        return None


def _latest_with_filter(versions: List[Version], predicate) -> Optional[Version]:
    filtered = [v for v in versions if predicate(v)]
    return filtered[-1] if filtered else None


def _group_candidates_from_pinned(all_versions: List[Version], pinned: Version) -> Dict[str, Optional[Version]]:
    # Assumes all_versions is sorted ascending
    cand_patch = _latest_with_filter(all_versions, lambda v: (v.release[:2] == pinned.release[:2] and v > pinned))
    cand_minor = _latest_with_filter(all_versions, lambda v: (len(v.release) > 0 and v.release[0] == pinned.release[0] and (len(v.release) > 1 and v.release[1] > (pinned.release[1] if len(pinned.release) > 1 else -1)) and (v.release[0] == pinned.release[0])))
    cand_major = _latest_with_filter(all_versions, lambda v: (len(v.release) > 0 and v.release[0] > (pinned.release[0] if len(pinned.release) > 0 else -1)))
    latest = all_versions[-1] if all_versions else None
    return {
        "patch": cand_patch,
        "minor": cand_minor,
        "major": cand_major,
        "latest": latest,
    }


def _candidates_from_range(all_versions: List[Version], spec: SpecifierSet) -> Dict[str, Optional[Version]]:
    within = [v for v in all_versions if spec.contains(v, prereleases=True)]
    within_latest = within[-1] if within else None
    latest = all_versions[-1] if all_versions else None
    return {
        "within_spec": within_latest,
        "latest": latest,
    }


def _release_python_compat(release_info: dict, target_python: Optional[str]) -> Dict[str, Any]:
    info = (release_info or {}).get("info") or {}
    requires_python = info.get("requires_python")
    ok, note = is_python_compatible(requires_python, target_python)
    return {
        "requires_python": requires_python,
        "is_compatible": ok,
        "note": note,
    }


def _candidate_entry(name: str, version: Version, client: PyPIClient, target_python: Optional[str], target_frameworks: Dict[str, str]) -> Dict[str, Any]:
    rel = client.get_release_metadata(name, version)
    py = _release_python_compat(rel, target_python)
    fw_warnings = framework_warnings_for_release(name, version, rel, target_frameworks)
    return {
        "to_version": str(version),
        "python_requires": py.get("requires_python"),
        "python_compatible": py.get("is_compatible"),
        "python_note": py.get("note"),
        "framework_warnings": fw_warnings,
    }


def suggest_upgrade_paths(parsed_requirements: List[Dict[str, Any]], target_python: Optional[str] = None, target_frameworks: Optional[Dict[str, str]] = None, include_prereleases: bool = False) -> Dict[str, Any]:
    client = PyPIClient()
    suggestions: List[Dict[str, Any]] = []
    errors: List[str] = []

    for item in parsed_requirements:
        name = item.get("name")
        name_norm = canonicalize_name(name or "")
        spec_str = item.get("specifier")
        pinned_s = item.get("pinned_version")
        pinned_v = _version_or_none(pinned_s)
        try:
            all_versions = client.get_all_versions(name, include_prereleases=include_prereleases)
        except Exception as e:
            all_versions = []
            errors.append(f"{name}: failed to fetch versions: {e}")
        
        pkg_entry: Dict[str, Any] = {
            "name": name,
            "name_normalized": name_norm,
            "current_spec": spec_str,
            "current_locked_version": str(pinned_v) if pinned_v else None,
            "available_versions_count": len(all_versions),
            "upgrade_paths": [],
            "latest": str(all_versions[-1]) if all_versions else None,
            "compatibility": {},
            "warnings": [],
        }

        if not all_versions:
            suggestions.append(pkg_entry)
            continue

        target_frameworks = target_frameworks or {}

        if pinned_v:
            groups = _group_candidates_from_pinned(all_versions, pinned_v)
            for kind in ("patch", "minor", "major"):
                cand = groups.get(kind)
                if cand and cand > pinned_v:
                    pkg_entry["upgrade_paths"].append({
                        "type": kind,
                        **_candidate_entry(name, cand, client, target_python, target_frameworks),
                    })
            # Always include latest if not already listed
            latest_v = groups.get("latest")
            if latest_v and all(str(p.get("to_version")) != str(latest_v) for p in pkg_entry["upgrade_paths"]):
                pkg_entry["upgrade_paths"].append({
                    "type": "latest",
                    **_candidate_entry(name, latest_v, client, target_python, target_frameworks),
                })
        else:
            spec = SpecifierSet(spec_str) if spec_str else None
            if spec:
                cands = _candidates_from_range(all_versions, spec)
                within = cands.get("within_spec")
                if within:
                    pkg_entry["upgrade_paths"].append({
                        "type": "within_spec",
                        **_candidate_entry(name, within, client, target_python, target_frameworks),
                    })
                latest_v = cands.get("latest")
                if latest_v and (not within or latest_v > within):
                    pkg_entry["upgrade_paths"].append({
                        "type": "latest",
                        **_candidate_entry(name, latest_v, client, target_python, target_frameworks),
                    })
            else:
                # No specifier given, propose latest
                latest_v = all_versions[-1]
                pkg_entry["upgrade_paths"].append({
                    "type": "latest",
                    **_candidate_entry(name, latest_v, client, target_python, target_frameworks),
                })

        # Add overall compatibility snapshot for the current pinned version if available
        if pinned_v:
            rel = client.get_release_metadata(name, pinned_v)
            py = _release_python_compat(rel, target_python)
            fw = framework_warnings_for_release(name, pinned_v, rel, target_frameworks)
            pkg_entry["compatibility"] = {
                "python": {
                    "requires_python": py.get("requires_python"),
                    "is_compatible": py.get("is_compatible"),
                    "note": py.get("note"),
                },
                "frameworks": fw,
            }
            pkg_entry["warnings"].extend(fw)

        # If target framework version conflicts with the user's specified constraint, surface warning
        if spec_str and canonicalize_name(name) in {canonicalize_name(k) for k in (target_frameworks or {}).keys()}:
            # The requirement is the framework itself
            tf_version = target_frameworks.get(name) or target_frameworks.get(name_norm)
            if tf_version:
                try:
                    tf_v = Version(str(tf_version))
                    spec = SpecifierSet(spec_str)
                    if not spec.contains(tf_v, prereleases=True):
                        pkg_entry["warnings"].append(
                            f"Your specifier '{spec_str}' for {name} does not include target {tf_v}."
                        )
                except Exception:
                    pass

        suggestions.append(pkg_entry)

    # Summary counts
    total = len(suggestions)
    with_paths = sum(1 for s in suggestions if s.get("upgrade_paths"))
    
    summary = {
        "total": total,
        "upgradable": with_paths,
        "no_upgrades": total - with_paths,
    }

    return {
        "summary": summary,
        "suggestions": suggestions,
        "errors": errors,
    }
