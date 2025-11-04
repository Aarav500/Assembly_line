import os
import json
from typing import Dict


def _parse_split_env(raw: str) -> Dict[str, float]:
    # Accept formats like "v1:0.7,v2:0.3" or "v1=0.7,v2=0.3" or JSON {"v1":0.7,"v2":0.3}
    if not raw:
        return {"v1": 0.5, "v2": 0.5}
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            return {str(k): float(v) for k, v in data.items()}
        except Exception:
            pass
    raw = raw.replace("=", ":")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    weights = {}
    for p in parts:
        if ":" not in p:
            continue
        k, v = p.split(":", 1)
        try:
            weights[k.strip()] = float(v.strip())
        except ValueError:
            continue
    if not weights:
        weights = {"v1": 0.5, "v2": 0.5}
    # Normalize to sum to 1
    total = sum(max(0.0, w) for w in weights.values())
    if total <= 0:
        weights = {"v1": 0.5, "v2": 0.5}
        total = 1.0
    weights = {k: max(0.0, v) / total for k, v in weights.items()}
    return weights


TRAFFIC_SPLIT = _parse_split_env(os.environ.get("TRAFFIC_SPLIT", "v1:0.7,v2:0.3"))
EXPERIMENT_ID = os.environ.get("EXPERIMENT_ID", "exp-001")
COOKIE_NAME = os.environ.get("COOKIE_NAME", "ab_variant")
COOKIE_TTL_SECONDS = int(os.environ.get("COOKIE_TTL_SECONDS", str(30 * 24 * 60 * 60)))
ALLOW_VARIANT_OVERRIDE = os.environ.get("ALLOW_VARIANT_OVERRIDE", "false").lower() in ("1", "true", "yes")
LOG_DIR = os.environ.get("LOG_DIR", "logs")

