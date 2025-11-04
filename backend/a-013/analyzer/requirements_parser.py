from __future__ import annotations
from typing import List, Tuple, Dict, Any
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def parse_requirements_text(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    items: List[Dict[str, Any]] = []
    errors: List[str] = []
    if not text:
        return items, errors
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r") or line.startswith("--requirement"):
            # Include files are not resolved here; user can inline or call API per file
            errors.append(f"Line {line_no}: include directives are not supported: {raw}")
            continue
        if line.startswith("-e") or line.startswith("--editable"):
            errors.append(f"Line {line_no}: editable installs are not supported: {raw}")
            continue
        try:
            req = Requirement(line)
        except Exception as e:
            errors.append(f"Line {line_no}: failed to parse requirement '{raw}': {e}")
            continue
        items.append(_req_to_item(req, raw))
    return items, errors


def parse_dependencies_json(deps: List[dict]) -> Tuple[List[Dict[str, Any]], List[str]]:
    items: List[Dict[str, Any]] = []
    errors: List[str] = []
    for idx, d in enumerate(deps, start=1):
        if not isinstance(d, dict):
            errors.append(f"Dep {idx}: expected object, got {type(d).__name__}")
            continue
        name = (d.get("name") or "").strip()
        spec = (d.get("spec") or "").strip()
        if not name:
            errors.append(f"Dep {idx}: missing name")
            continue
        line = name if not spec else f"{name}{spec}"
        try:
            req = Requirement(line)
        except Exception as e:
            errors.append(f"Dep {idx}: invalid requirement '{line}': {e}")
            continue
        items.append(_req_to_item(req, line))
    return items, errors


def _req_to_item(req: Requirement, raw_line: str) -> Dict[str, Any]:
    pinned_version = None
    pin_ops = {s.operator for s in req.specifier}
    if "==" in pin_ops or "===" in pin_ops:
        # Choose the first exact pin in appearance order
        for s in req.specifier:
            if s.operator in ("==", "==="):
                pinned_version = s.version
                break
    return {
        "name": req.name,
        "name_normalized": canonicalize_name(req.name),
        "specifier": str(req.specifier) if str(req.specifier) else None,
        "pinned_version": pinned_version,
        "marker": str(req.marker) if req.marker else None,
        "line": raw_line,
    }

