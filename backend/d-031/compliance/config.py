import json
import os
from typing import Any, Dict, Optional

import yaml


_DEFAULT_CONFIG_PATHS = [
    os.path.join("config", "compliance.yaml"),
    os.path.join("config", "compliance.yml"),
    os.path.join("config", "compliance.json"),
]


def _load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(path: Optional[str] = None, override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg_path = (
        path
        or os.getenv("COMPLIANCE_CONFIG")
        or next((p for p in _DEFAULT_CONFIG_PATHS if os.path.exists(p)), None)
    )

    config: Dict[str, Any] = {}

    if cfg_path and os.path.exists(cfg_path):
        if cfg_path.endswith((".yaml", ".yml")):
            config = _load_yaml(cfg_path)
        elif cfg_path.endswith(".json"):
            config = _load_json(cfg_path)
        else:
            raise ValueError(f"Unsupported config format: {cfg_path}")

    # Merge env var overrides (JSON)
    env_override = os.getenv("COMPLIANCE_CONFIG_JSON")
    if env_override:
        try:
            config = _deep_merge(config, json.loads(env_override))
        except Exception as e:
            raise ValueError(f"Invalid COMPLIANCE_CONFIG_JSON: {e}")

    if override:
        config = _deep_merge(config, override)

    return config


def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(a)
    for k, v in b.items():
        if (
            k in result
            and isinstance(result[k], dict)
            and isinstance(v, dict)
        ):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result

