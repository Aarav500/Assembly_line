from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from packaging.version import Version, InvalidVersion
from packaging.specifiers import SpecifierSet
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def is_python_compatible(requires_python: Optional[str], target_python: Optional[str]) -> Tuple[bool, Optional[str]]:
    if not requires_python or not requires_python.strip():
        return True, None
    try:
        spec = SpecifierSet(requires_python)
    except Exception:
        # If malformed, be permissive but return note
        return True, f"Unparseable requires_python: {requires_python}"
    if not target_python:
        return True, None
    try:
        pyv = Version(target_python)
    except InvalidVersion:
        return True, f"Unparseable target_python: {target_python}"
    ok = spec.contains(pyv, prereleases=True)
    return ok, None


def parse_requires_dist(requirements: Optional[List[str]]) -> List[Requirement]:
    reqs: List[Requirement] = []
    if not requirements:
        return reqs
    for r in requirements:
        try:
            reqs.append(Requirement(r))
        except Exception:
            # ignore invalid entry
            continue
    return reqs


def framework_warnings_for_release(name: str, version: Version, release_info: dict, target_frameworks: Dict[str, str]) -> List[str]:
    warnings: List[str] = []
    info = (release_info or {}).get("info") or {}
    requires_dist = parse_requires_dist(info.get("requires_dist") or [])

    for fwk, fwk_ver in (target_frameworks or {}).items():
        fwk_norm = canonicalize_name(fwk)
        if not fwk_ver:
            continue
        try:
            fwk_v = Version(str(fwk_ver))
        except InvalidVersion:
            warnings.append(f"Target framework '{fwk}' version '{fwk_ver}' is not a valid version.")
            continue

        if canonicalize_name(name) == fwk_norm:
            # This dependency IS the framework. Check if candidate equals or diverges from target.
            try:
                cand_v = Version(str(version))
            except InvalidVersion:
                continue
            if cand_v != fwk_v:
                warnings.append(f"Target {fwk} is {fwk_v}, candidate {cand_v} differs. Ensure app compatibility.")
            continue

        # Check if package declares a requirement on the framework
        for req in requires_dist:
            if canonicalize_name(req.name) == fwk_norm:
                spec_str = str(req.specifier) if str(req.specifier) else None
                if spec_str:
                    try:
                        spec = req.specifier
                        if not spec.contains(fwk_v, prereleases=True):
                            warnings.append(
                                f"{name} {version} requires {fwk} {spec_str} which does not include target {fwk_v}."
                            )
                    except Exception:
                        # best effort
                        warnings.append(
                            f"{name} {version} declares {fwk} dependency '{spec_str}', unable to verify against {fwk_v}."
                        )
                else:
                    # Requires framework but without version pin: generally okay
                    pass
    return warnings

