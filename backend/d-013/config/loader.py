from __future__ import annotations
import os
import re
from copy import deepcopy
from typing import Any, Dict
import yaml


_VAR_RE = re.compile(r"^\$\{([^:}]+)(?::-(.*))?\}$")


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def _deep_merge(a: dict, b: dict) -> dict:
    res = deepcopy(a)
    for k, v in (b or {}).items():
        if k in res and isinstance(res[k], dict) and isinstance(v, dict):
            res[k] = _deep_merge(res[k], v)
        else:
            res[k] = deepcopy(v)
    return res


def _subst(value: Any) -> Any:
    if isinstance(value, str):
        m = _VAR_RE.match(value)
        if m:
            var, default = m.group(1), m.group(2)
            return os.getenv(var, default if default is not None else "")
        return value
    if isinstance(value, list):
        return [_subst(v) for v in value]
    if isinstance(value, dict):
        return {k: _subst(v) for k, v in value.items()}
    return value


def _normalize_policy(cfg: Dict[str, Any]) -> Dict[str, Any]:
    policy = cfg.get("policy", {}) or {}

    # Normalize api_keys possibly provided as comma-separated string
    auth = policy.get("auth", {}) or {}
    api_keys = auth.get("api_keys", [])
    if isinstance(api_keys, str):
        auth["api_keys"] = [k.strip() for k in api_keys.split(",") if k.strip()]
        policy["auth"] = auth

    # Normalize allowed_origins possibly provided as comma-separated string
    allowed = policy.get("allowed_origins")
    if isinstance(allowed, str):
        policy["allowed_origins"] = [o.strip() for o in allowed.split(",") if o.strip()]

    cfg["policy"] = policy
    return cfg


def load_config(env: str) -> Dict[str, Any]:
    base_path = os.path.join(os.path.dirname(__file__), "base.yaml")
    overlays_dir = os.path.join(os.path.dirname(__file__), "overlays")
    overlay_path = os.path.join(overlays_dir, f"{env}.yaml")

    base_cfg = _load_yaml(base_path)
    if os.path.exists(overlay_path):
        overlay_cfg = _load_yaml(overlay_path)
    else:
        overlay_cfg = {}

    merged = _deep_merge(base_cfg, overlay_cfg)

    # Substitute environment variables
    merged = _subst(merged)

    # Normalize policy shapes
    merged = _normalize_policy(merged)

    return merged

