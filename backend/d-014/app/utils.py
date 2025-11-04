import re
import time
import json
from typing import Any, Dict, List, Optional
import yaml
from .config import config


def k8s_name(value: str, prefix: Optional[str] = None, max_len: int = 63) -> str:
    if not value:
        value = "job"
    value = value.lower()
    value = re.sub(r"[^a-z0-9-]", "-", value)
    value = re.sub(r"-+", "-", value)
    value = value.strip("-") or "job"
    if prefix:
        prefix = re.sub(r"[^a-z0-9-]", "-", prefix.lower()).strip("-")
        base = f"{prefix}-{value}"
    else:
        base = value
    if len(base) > max_len:
        base = base[:max_len].rstrip("-")
    return base or "job"


def now_suffix() -> str:
    return time.strftime("%Y%m%d%H%M%S")


def merge_dicts(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    res: Dict[str, Any] = {}
    if a:
        res.update(a)
    if b:
        res.update(b)
    return res


def normalize_env(env: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not env:
        return []
    out: List[Dict[str, Any]] = []
    for e in env:
        if not isinstance(e, dict) or "name" not in e or not e["name"]:
            continue
        item: Dict[str, Any] = {"name": str(e["name"])[:253]}
        if "valueFrom" in e:
            item["valueFrom"] = e["valueFrom"]
        elif "value" in e:
            item["value"] = str(e["value"])
        out.append(item)
    return out


def parse_json_env(value: str) -> Optional[Any]:
    try:
        return json.loads(value)
    except Exception:
        return None


def yaml_dump(obj: Any) -> str:
    return yaml.safe_dump(obj, sort_keys=False)


def boolish(v: Any, default: bool = False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


def image_pull_policy_for(image: str) -> str:
    if ":latest" in image or image.endswith(":latest"):
        return "Always"
    return config.DEFAULT_IMAGE_PULL_POLICY


def inject_optional_pod_scheduling(spec: Dict[str, Any], payload: Dict[str, Any]) -> None:
    node_selector = payload.get("nodeSelector")
    tolerations = payload.get("tolerations")
    affinity = payload.get("affinity")

    # From env defaults if not provided
    if not node_selector and config.DEFAULT_NODE_SELECTOR:
        # parse KEY=VAL pairs
        parts = [p.strip() for p in config.DEFAULT_NODE_SELECTOR.split(",") if p.strip()]
        if parts:
            ns: Dict[str, str] = {}
            for p in parts:
                if "=" in p:
                    k, v = p.split("=", 1)
                    ns[k.strip()] = v.strip()
            if ns:
                node_selector = ns

    if not tolerations and config.DEFAULT_TOLERATIONS:
        tolerations = parse_json_env(config.DEFAULT_TOLERATIONS)

    if not affinity and config.DEFAULT_AFFINITY:
        affinity = parse_json_env(config.DEFAULT_AFFINITY)

    if node_selector:
        spec["nodeSelector"] = node_selector
    if tolerations:
        spec["tolerations"] = tolerations
    if affinity:
        spec["affinity"] = affinity

