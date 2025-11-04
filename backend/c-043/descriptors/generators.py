import copy
from typing import Any, Dict
import yaml


def normalize_appengine_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg = copy.deepcopy(cfg or {})
    defaults = {
        "service": "default",
        "runtime": "python311",
        "entrypoint": "gunicorn -b :$PORT wsgi:app",
        "instance_class": "F2",
        "automatic_scaling": {
            "target_cpu_utilization": 0.65,
            "min_instances": 0,
            "max_instances": 2,
        },
        "env_variables": {},
        "handlers": [
            {"url": "/static", "static_dir": "static"}
        ],
    }

    merged = {**defaults, **{k: v for k, v in cfg.items() if v is not None}}

    # Merge nested dicts
    for key in ["automatic_scaling", "env_variables"]:
        if key in cfg and isinstance(cfg[key], dict):
            merged[key] = {**defaults.get(key, {}), **cfg[key]}

    # Handlers: replace if explicitly provided
    if "handlers" in cfg and isinstance(cfg["handlers"], list):
        merged["handlers"] = cfg["handlers"]

    return merged


def generate_appengine_yaml(cfg: Dict[str, Any]) -> str:
    doc: Dict[str, Any] = {}
    if cfg.get("service"):
        doc["service"] = cfg["service"]
    doc["runtime"] = cfg.get("runtime", "python311")
    doc["entrypoint"] = cfg.get("entrypoint", "gunicorn -b :$PORT wsgi:app")

    if cfg.get("instance_class"):
        doc["instance_class"] = cfg["instance_class"]

    if cfg.get("automatic_scaling"):
        doc["automatic_scaling"] = cfg["automatic_scaling"]

    if cfg.get("env_variables"):
        doc["env_variables"] = cfg["env_variables"]

    if cfg.get("handlers"):
        doc["handlers"] = cfg["handlers"]

    return yaml.safe_dump(doc, sort_keys=False)


def normalize_serverless_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg = copy.deepcopy(cfg or {})
    defaults = {
        "service": "flask-app",
        "frameworkVersion": ">=3.0.0",
        "provider": {
            "name": "aws",
            "runtime": "python3.11",
            "stage": "dev",
            "region": "us-east-1",
            "memorySize": 512,
            "timeout": 30,
            "environment": {},
        },
        "functions": {
            "app": {
                "handler": "wsgi_handler.handler",
                "events": [
                    {"httpApi": "*"}
                ],
            }
        },
        "plugins": [
            "serverless-python-requirements",
            "serverless-wsgi",
        ],
        "custom": {
            "wsgi": {
                "app": "wsgi.app",
                "packRequirements": False,
            },
            "pythonRequirements": {
                "dockerizePip": True,
                "slim": True,
            },
        },
        "package": {
            "exclude": [
                "node_modules/**",
                "venv/**",
                "sample_configs/**",
                "tests/**",
                ".git/**",
                "__pycache__/**",
                "*.md",
            ]
        },
    }

    merged = {**defaults, **{k: v for k, v in cfg.items() if v is not None}}

    # Merge provider
    if isinstance(cfg.get("provider"), dict):
        merged["provider"] = {**defaults["provider"], **cfg["provider"]}
        if isinstance(cfg["provider"].get("environment"), dict):
            merged["provider"]["environment"] = {
                **defaults["provider"].get("environment", {}),
                **cfg["provider"]["environment"],
            }

    # Functions: replace if provided
    if isinstance(cfg.get("functions"), dict):
        merged["functions"] = cfg["functions"]

    # Plugins: replace if provided
    if isinstance(cfg.get("plugins"), list):
        merged["plugins"] = cfg["plugins"]

    # Custom: deep-ish merge for wsgi and pythonRequirements
    if isinstance(cfg.get("custom"), dict):
        merged["custom"] = {**defaults["custom"], **cfg["custom"]}
        if isinstance(cfg["custom"].get("wsgi"), dict):
            merged["custom"]["wsgi"] = {**defaults["custom"].get("wsgi", {}), **cfg["custom"]["wsgi"]}
        if isinstance(cfg["custom"].get("pythonRequirements"), dict):
            merged["custom"]["pythonRequirements"] = {
                **defaults["custom"].get("pythonRequirements", {}),
                **cfg["custom"]["pythonRequirements"],
            }

    # Package: shallow merge
    if isinstance(cfg.get("package"), dict):
        merged["package"] = {**defaults["package"], **cfg["package"]}

    return merged


def generate_serverless_yaml(cfg: Dict[str, Any]) -> str:
    doc: Dict[str, Any] = {}
    doc["service"] = cfg.get("service", "flask-app")
    if cfg.get("frameworkVersion"):
        doc["frameworkVersion"] = cfg["frameworkVersion"]
    if cfg.get("provider"):
        doc["provider"] = cfg["provider"]
    if cfg.get("functions"):
        doc["functions"] = cfg["functions"]
    if cfg.get("plugins"):
        doc["plugins"] = cfg["plugins"]
    if cfg.get("custom"):
        doc["custom"] = cfg["custom"]
    if cfg.get("package"):
        doc["package"] = cfg["package"]

    return yaml.safe_dump(doc, sort_keys=False)

