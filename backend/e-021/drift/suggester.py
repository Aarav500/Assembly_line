import difflib
import os
from typing import Dict, Any, List

import yaml

from drift.detector import load_desired_state


def _read_file(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _serialize_desired(resources_map: Dict[str, Any]) -> str:
    resources = []
    for rid, r in sorted(resources_map.items()):
        resources.append({
            "id": rid,
            "type": r.get("type"),
            "name": r.get("name"),
            "attributes": r.get("attributes", {}),
        })
    doc = {"resources": resources}
    return yaml.safe_dump(doc, sort_keys=False)


def build_remediation_suggestions(report: Dict[str, Any], desired_path: str, strategy: str = "code_to_actual") -> Dict[str, Any]:
    desired = load_desired_state(desired_path)
    desired_map = desired.get("resources", {})

    # Clone map to mutate as "proposed"
    proposed = {k: {**v, "attributes": dict(v.get("attributes", {}))} for k, v in desired_map.items()}

    commands: List[str] = []
    notes: List[str] = []

    if strategy == "code_to_actual":
        # Update code to reflect actual state
        for change in report.get("changes", []):
            rid = change["id"]
            actual_attrs = change.get("actual_attributes", {})
            if rid in proposed:
                proposed[rid]["attributes"] = actual_attrs
        for rid in report.get("extra_in_actual", []):
            notes.append(f"Consider importing or adding resource {rid} to code.")
        for rid in report.get("missing_in_actual", []):
            # Resource defined in code but missing in cloud; keep or remove?
            notes.append(f"Resource {rid} is defined in code but missing in actual. Decide to recreate or remove from code.")
    elif strategy == "actual_to_code":
        # Suggest commands to reconcile actual to desired
        for change in report.get("changes", []):
            rid = change["id"]
            commands.append(f"Revert drift for {rid}: apply desired attributes via IaC tool (e.g., terraform apply)")
        for rid in report.get("extra_in_actual", []):
            commands.append(f"Remove unmanaged resource {rid} from actual (or import into code)")
        for rid in report.get("missing_in_actual", []):
            commands.append(f"Create missing resource {rid} in actual via IaC apply")
        # No file patches needed for actual_to_code, but we include preview diff of no changes
    else:
        raise ValueError("Unsupported strategy; use code_to_actual or actual_to_code")

    before_text = _read_file(desired_path)
    after_text = before_text

    if strategy == "code_to_actual":
        after_text = _serialize_desired(proposed)

    diff = "".join(
        difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=desired_path + " (before)",
            tofile=desired_path + " (after)",
        )
    )

    file_patches = []
    if strategy == "code_to_actual" and before_text != after_text:
        file_patches.append({
            "path": desired_path,
            "before": before_text,
            "after": after_text,
            "diff": diff,
        })

    return {
        "strategy": strategy,
        "file_patches": file_patches,
        "commands": commands,
        "notes": notes,
        "report_summary": report.get("summary", {}),
    }

