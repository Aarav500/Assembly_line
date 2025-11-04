import os
import re
from copy import deepcopy
from typing import Any

import yaml
from pydantic import ValidationError

from .secret_resolver import SecretResolver
from .settings import AppConfig


PLACEHOLDER_PATTERN = re.compile(r"\$\{(?P<src>env|vault|aws-sm):(?P<id>[^}|]+?)(?:\|(?P<default>[^}]*))?\}")


def deep_merge(a: dict, b: dict) -> dict:
    """Recursively merge dict b into dict a, returning a new dict."""
    result = deepcopy(a)
    for k, v in (b or {}).items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = deepcopy(v)
    return result


def _replace_placeholders_in_string(s: str, resolver: SecretResolver) -> str:
    def _sub(match: re.Match) -> str:
        src = match.group("src")
        ident = match.group("id")
        default = match.group("default")
        try:
            if src == "env":
                return resolver.resolve_env(ident, default)
            elif src == "vault":
                path, key = (ident.split("#", 1) + [None])[:2]
                return resolver.resolve_vault(path, key, default)
            elif src == "aws-sm":
                secret_id, json_key = (ident.split("#", 1) + [None])[:2]
                return resolver.resolve_aws(secret_id, json_key, default)
        except Exception:
            if default is not None:
                return default
            raise
        return match.group(0)

    # Replace all placeholders in the string
    return PLACEHOLDER_PATTERN.sub(_sub, s)


def _interpolate(obj: Any, resolver: SecretResolver) -> Any:
    if isinstance(obj, dict):
        return {k: _interpolate(v, resolver) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate(i, resolver) for i in obj]
    if isinstance(obj, str):
        return _replace_placeholders_in_string(obj, resolver)
    return obj


def load_yaml_file(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a mapping at the root")
    return data


def load_config(config_dir: str, env: str) -> dict:
    base_path = os.path.join(config_dir, "base.yaml")
    env_path = os.path.join(config_dir, f"{env}.yaml")

    base_cfg = load_yaml_file(base_path)
    env_cfg = load_yaml_file(env_path)

    merged = deep_merge(base_cfg, env_cfg)

    resolver = SecretResolver()
    interpolated = _interpolate(merged, resolver)
    return interpolated


def load_and_validate_config(config_dir: str, env: str) -> AppConfig:
    raw = load_config(config_dir, env)
    try:
        cfg = AppConfig.model_validate(raw)
    except ValidationError as ve:
        # Re-raise with a clearer message
        raise RuntimeError(f"Configuration validation failed: {ve}")
    return cfg

