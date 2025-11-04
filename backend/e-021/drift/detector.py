import copy
import json
import os
import subprocess
from datetime import datetime
from typing import Dict, List, Any

import yaml

from utils.io import read_json_file


def load_desired_state(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Desired state file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # Normalize to dict with resources map by id
    resources = data.get("resources") or []
    res_map = {}
    for r in resources:
        rid = r.get("id") or f"{r.get('type')}.{r.get('name')}"
        res_map[rid] = {
            "id": rid,
            "type": r.get("type"),
            "name": r.get("name"),
            "attributes": r.get("attributes", {}),
        }
    return {"resources": res_map}


def _load_actual_state_from_file(path: str) -> Dict[str, Any]:
    data = read_json_file(path)
    res_map = {}
    for r in data.get("resources", []):
        rid = r.get("id") or r.get("address") or f"{r.get('type')}.{r.get('name')}"
        res_map[rid] = {
            "id": rid,
            "type": r.get("type"),
            "name": r.get("name"),
            "attributes": r.get("attributes", r.get("values", {})),
        }
    return {"resources": res_map}


def _load_actual_state_from_inline(obj: Dict[str, Any]) -> Dict[str, Any]:
    res_map = {}
    for r in obj.get("resources", []):
        rid = r.get("id") or r.get("address") or f"{r.get('type')}.{r.get('name')}"
        res_map[rid] = {
            "id": rid,
            "type": r.get("type"),
            "name": r.get("name"),
            "attributes": r.get("attributes", r.get("values", {})),
        }
    return {"resources": res_map}


def _load_actual_state_from_terraform_show_json(workdir: str) -> Dict[str, Any]:
    # Runs `terraform show -json` in the given directory and parses resource values
    if not os.path.isdir(workdir):
        raise FileNotFoundError(f"Terraform working directory not found: {workdir}")
    try:
        proc = subprocess.run(
            ["terraform", "show", "-json"],
            cwd=workdir,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise RuntimeError("terraform not found in PATH; install Terraform or use provider=file/inline")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"terraform show failed: {e.stderr}")

    data = json.loads(proc.stdout)
    # Extract from values.root_module.resources if available
    res_map = {}
    values = data.get("values", {})
    root = values.get("root_module", {})
    def _collect(mod, prefix=""):
        for r in mod.get("resources", []):
            address = r.get("address") or f"{r.get('type')}.{r.get('name')}"
            rid = address
            res_map[rid] = {
                "id": rid,
                "type": r.get("type"),
                "name": r.get("name"),
                "attributes": r.get("values", {}),
            }
        for child in mod.get("child_modules", []):
            _collect(child, prefix)
    _collect(root)
    return {"resources": res_map}


def _dict_diff(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    # Shallow dict diff by keys and simple scalar values; nested dicts are compared recursively to one level
    diff = {"changed": {}, "only_in_a": {}, "only_in_b": {}}
    a_keys = set(a.keys())
    b_keys = set(b.keys())
    for k in a_keys - b_keys:
        diff["only_in_a"][k] = a[k]
    for k in b_keys - a_keys:
        diff["only_in_b"][k] = b[k]
    for k in a_keys & b_keys:
        av = a[k]
        bv = b[k]
        if isinstance(av, dict) and isinstance(bv, dict):
            if av != bv:
                # shallow compare fields
                nested = _dict_diff(av, bv)
                if nested["changed"] or nested["only_in_a"] or nested["only_in_b"]:
                    diff["changed"][k] = nested
        else:
            if av != bv:
                diff["changed"][k] = {"from": av, "to": bv}
    return diff


def detect_drift(
    desired_state: Dict[str, Any],
    provider: str = "file",
    provider_options: Dict[str, Any] = None,
    inline_actual_state: Dict[str, Any] = None,
) -> Dict[str, Any]:
    provider_options = provider_options or {}

    if provider == "file":
        path = provider_options.get("path") or provider_options.get("actual_state_path") or "data/actual_state.sample.json"
        actual_state = _load_actual_state_from_file(path)
    elif provider == "inline":
        if not inline_actual_state:
            raise ValueError("inline actual_state is required for provider=inline")
        actual_state = _load_actual_state_from_inline(inline_actual_state)
    elif provider == "terraform_show":
        workdir = provider_options.get("workdir") or "."
        actual_state = _load_actual_state_from_terraform_show_json(workdir)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    desired_map: Dict[str, Any] = desired_state.get("resources", {})
    actual_map: Dict[str, Any] = actual_state.get("resources", {})

    desired_ids = set(desired_map.keys())
    actual_ids = set(actual_map.keys())

    missing_in_actual = sorted(list(desired_ids - actual_ids))
    extra_in_actual = sorted(list(actual_ids - desired_ids))

    changes = []
    for rid in sorted(list(desired_ids & actual_ids)):
        d = desired_map[rid]
        a = actual_map[rid]
        attr_diff = _dict_diff(d.get("attributes", {}), a.get("attributes", {}))
        if attr_diff["changed"] or attr_diff["only_in_a"] or attr_diff["only_in_b"]:
            changes.append({
                "id": rid,
                "type": d.get("type") or a.get("type"),
                "name": d.get("name") or a.get("name"),
                "attribute_diff": attr_diff,
                "desired_attributes": d.get("attributes", {}),
                "actual_attributes": a.get("attributes", {}),
            })

    summary = {
        "missing_in_actual": len(missing_in_actual),
        "extra_in_actual": len(extra_in_actual),
        "changed": len(changes),
        "total_desired": len(desired_ids),
        "total_actual": len(actual_ids),
    }

    report = {
        "id": None,  # to be filled by storage
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "provider": provider,
        "summary": summary,
        "missing_in_actual": missing_in_actual,
        "extra_in_actual": extra_in_actual,
        "changes": changes,
    }
    return report

