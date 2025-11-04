import os
import yaml
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "allow_patterns": [],
    "ignore_paths": [
        ".git/*",
        "node_modules/*",
        "venv/*",
        ".venv/*",
        "__pycache__/*",
        "*.png",
        "*.jpg",
        "*.jpeg",
        "*.gif",
        "*.pdf",
        "*.zip",
        "*.jar",
        "*.bin",
    ],
    "enable_high_entropy": True,
    "entropy_threshold": 4.5,
    "excluded_rules": [],
    "severity_threshold": "medium",
}


def load_config(path: str = ".secretscan.yml") -> Dict[str, Any]:
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
                for k, v in loaded.items():
                    cfg[k] = v
        except Exception:
            # If config parsing fails, fallback to defaults
            pass
    return cfg

