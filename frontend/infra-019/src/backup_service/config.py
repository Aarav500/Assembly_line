import os
from typing import Any, Dict
import yaml

DEFAULTS = {
    "global": {
        "primary_region": os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
        "dr_region": None,
        "profile_name": os.getenv("AWS_PROFILE"),
        "role_arn": None,
        "external_id": None,
        "kms_key_id": None,
        "dry_run": False,
    },
    "ebs": {
        "enabled": True,
        "tag_filters": [],
        "retention_days": 14,
        "wait_for_completion": False,
        "copy_to_dr": False,
    },
    "rds": {
        "enabled": True,
        "instance_identifiers": [],
        "tag_filters": [],
        "retention_days": 7,
        "wait_for_completion": False,
        "copy_to_dr": False,
    },
}


def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(a)
    for k, v in b.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(path: str | None = None) -> Dict[str, Any]:
    cfg_path = path or os.getenv("BACKUP_CONFIG")
    cfg: Dict[str, Any] = {}
    if cfg_path and os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    return deep_merge(DEFAULTS, cfg)

