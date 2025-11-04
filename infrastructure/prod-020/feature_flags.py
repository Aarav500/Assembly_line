from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from config import GLOBAL_KILL_SWITCH
from utils import stable_bucket, now_iso


@dataclass
class FeatureFlag:
    name: str
    enabled: bool = False
    rollout: float = 0.0  # percent 0..100
    kill_switch: bool = False
    description: str | None = None
    updated_at: str | None = None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "FeatureFlag":
        return FeatureFlag(
            name=d.get("name"),
            enabled=bool(d.get("enabled", False)),
            rollout=float(d.get("rollout", 0.0)),
            kill_switch=bool(d.get("kill_switch", False)),
            description=d.get("description"),
            updated_at=d.get("updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def decide_flag(flag: FeatureFlag, user_id: str) -> Dict[str, Any]:
    # Global kill switch overrides everything
    if GLOBAL_KILL_SWITCH:
        return {
            "flag": flag.name,
            "user_id": user_id,
            "on": False,
            "reason": "global_kill_switch",
            "bucket": None,
            "rollout": flag.rollout,
            "kill_switch": True,
            "enabled": flag.enabled,
            "timestamp": now_iso(),
        }

    # Emergency kill switch at flag level
    if flag.kill_switch:
        return {
            "flag": flag.name,
            "user_id": user_id,
            "on": False,
            "reason": "kill_switch",
            "bucket": None,
            "rollout": flag.rollout,
            "kill_switch": True,
            "enabled": flag.enabled,
            "timestamp": now_iso(),
        }

    if not flag.enabled:
        return {
            "flag": flag.name,
            "user_id": user_id,
            "on": False,
            "reason": "disabled",
            "bucket": None,
            "rollout": flag.rollout,
            "kill_switch": False,
            "enabled": flag.enabled,
            "timestamp": now_iso(),
        }

    # Gradual rollout logic
    bucket = stable_bucket("flag", flag.name, str(user_id))
    threshold = (flag.rollout or 0.0) / 100.0
    is_on = bucket < threshold

    return {
        "flag": flag.name,
        "user_id": user_id,
        "on": bool(is_on),
        "reason": "rollout" if is_on else "rollout_holdout",
        "bucket": bucket,
        "rollout": flag.rollout,
        "kill_switch": False,
        "enabled": flag.enabled,
        "timestamp": now_iso(),
    }

