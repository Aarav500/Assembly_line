from __future__ import annotations
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


@dataclass
class RequiredFeature:
    name: str
    require_enabled: bool


class ManifestLoadError(Exception):
    pass


def _load_file(path: str) -> Any:
    if not os.path.exists(path):
        raise ManifestLoadError(f"File not found: {path}")
    _, ext = os.path.splitext(path)
    with open(path, "r", encoding="utf-8") as f:
        if ext.lower() in (".yaml", ".yml"):
            if yaml is None:
                raise ManifestLoadError("PyYAML is required to load YAML files")
            return yaml.safe_load(f) or {}
        return json.load(f)


def load_manifest(path: str) -> Dict[str, Any]:
    data = _load_file(path)
    if not isinstance(data, dict):
        raise ManifestLoadError("Manifest root must be a mapping/object")
    return data


def load_required_features(path: str) -> List[RequiredFeature]:
    data = _load_file(path)
    if not isinstance(data, dict):
        raise ManifestLoadError("Required features file root must be a mapping/object")

    enforce_default = bool(data.get("enforce_enabled_by_default", False))
    features = data.get("features")
    if features is None:
        # Support shorthand: top-level list
        if isinstance(data, list):
            features = data
        else:
            raise ManifestLoadError("Required features file must contain 'features' list or be a list")

    reqs: List[RequiredFeature] = []

    if isinstance(features, list):
        for item in features:
            if isinstance(item, str):
                reqs.append(RequiredFeature(name=item, require_enabled=enforce_default))
            elif isinstance(item, dict):
                name = item.get("name")
                if not isinstance(name, str) or not name:
                    raise ManifestLoadError("Each feature entry must include a non-empty 'name'")
                require_enabled = item.get("require_enabled")
                if require_enabled is None:
                    require_enabled = enforce_default
                reqs.append(RequiredFeature(name=name, require_enabled=bool(require_enabled)))
            else:
                raise ManifestLoadError("Invalid feature entry; must be string or object")
    else:
        raise ManifestLoadError("'features' must be a list")

    return reqs


def _coerce_bool(val: Any) -> Optional[bool]:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        lower = val.strip().lower()
        if lower in ("true", "yes", "1", "on", "enabled"):
            return True
        if lower in ("false", "no", "0", "off", "disabled"):
            return False
    return None


def extract_feature_states(manifest: Dict[str, Any], features_key: str = "features") -> Dict[str, Optional[bool]]:
    if features_key not in manifest:
        return {}
    feats = manifest[features_key]
    states: Dict[str, Optional[bool]] = {}

    if isinstance(feats, dict):
        for name, meta in feats.items():
            enabled: Optional[bool] = None
            if isinstance(meta, dict):
                enabled = _coerce_bool(meta.get("enabled"))
            elif isinstance(meta, bool):
                enabled = meta
            states[str(name)] = enabled
        return states

    if isinstance(feats, list):
        for item in feats:
            if isinstance(item, str):
                states[item] = None
            elif isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name:
                    states[name] = _coerce_bool(item.get("enabled"))
            # else: ignore unsupported entries
        return states

    # Unknown structure
    return {}


def compare_required_features(
    states: Dict[str, Optional[bool]],
    required: Iterable[RequiredFeature],
) -> Tuple[List[str], List[str]]:
    missing: List[str] = []
    disabled: List[str] = []

    for rf in required:
        present = rf.name in states
        if not present:
            missing.append(rf.name)
            continue
        if rf.require_enabled:
            enabled = states.get(rf.name)
            if enabled is False:
                disabled.append(rf.name)
            elif enabled is None:
                # absent enabled flag counts as a failure if required
                disabled.append(rf.name)
    return missing, disabled


def load_base_manifest_from_git(path_in_repo: str, base_ref: str) -> Optional[Dict[str, Any]]:
    try:
        content = subprocess.check_output(["git", "show", f"{base_ref}:{path_in_repo}"], text=True)
    except Exception:
        return None

    # Determine parser by extension
    _, ext = os.path.splitext(path_in_repo)
    try:
        if ext.lower() in (".yaml", ".yml"):
            if yaml is None:
                return None
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)
    except Exception:
        return None

    if isinstance(data, dict):
        return data
    return None


def compare_removals_against_base(
    current_states: Dict[str, Optional[bool]],
    base_states: Dict[str, Optional[bool]],
    required: Iterable[RequiredFeature],
) -> List[str]:
    required_names = {r.name for r in required}
    removed_required: List[str] = []
    for name in required_names:
        if name in base_states and name not in current_states:
            removed_required.append(name)
    return removed_required


def run_check(
    manifest_path: str,
    required_path: str,
    features_key: str = "features",
    base_ref: Optional[str] = None,
) -> Dict[str, Any]:
    manifest = load_manifest(manifest_path)
    required = load_required_features(required_path)
    states = extract_feature_states(manifest, features_key=features_key)

    missing, disabled = compare_required_features(states, required)

    removed_required: List[str] = []
    if base_ref:
        base_manifest = load_base_manifest_from_git(manifest_path, base_ref)
        if base_manifest is not None:
            base_states = extract_feature_states(base_manifest, features_key=features_key)
            removed_required = compare_removals_against_base(states, base_states, required)

    ok = not missing and not disabled and not removed_required

    return {
        "ok": ok,
        "missing_required_features": missing,
        "disabled_required_features": disabled,
        "removed_required_features_vs_base": removed_required,
        "checked_manifest_path": manifest_path,
        "required_features_path": required_path,
        "features_key": features_key,
        "base_ref": base_ref,
    }

