from typing import Dict, Any, List
import os
from .duplicate_detection import find_duplicates
from .dead_code import find_dead_code

SUPPORTED = {"duplicate", "dead_code"}


def run_passes(path: str, passes: List[str] | None = None, options: Dict[str, Any] | None = None) -> Dict[str, Any]:
    passes = passes or ["duplicate", "dead_code"]
    options = options or {}

    unknown = [p for p in passes if p not in SUPPORTED]
    if unknown:
        raise ValueError(f"Unsupported passes requested: {unknown}")

    # Normalize path
    path = os.path.abspath(path)

    results: Dict[str, Any] = {"path": path, "results": {}, "summary": {}}

    if "duplicate" in passes:
        dup_options = options.get("duplicate", {})
        results["results"]["duplicate"] = find_duplicates(path, dup_options)

    if "dead_code" in passes:
        dc_options = options.get("dead_code", {})
        results["results"]["dead_code"] = find_dead_code(path, dc_options)

    # Add simple summary
    dsum = results["results"].get("duplicate", {}).get("summary", {})
    csum = results["results"].get("dead_code", {}).get("summary", {})
    results["summary"] = {
        "files_scanned": max(dsum.get("files_scanned", 0), csum.get("files_scanned", 0)),
        "duplicate_groups": dsum.get("duplicate_groups", 0),
        "dead_items": csum.get("dead_items", 0),
        "errors": (dsum.get("errors", 0) + csum.get("errors", 0)),
    }

    return results

