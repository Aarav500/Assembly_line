from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

from config import GLOBAL_KILL_SWITCH
from utils import stable_bucket, now_iso


@dataclass
class Variation:
    name: str
    weight: float


@dataclass
class Experiment:
    name: str
    variations: List[Variation]
    enabled: bool = False
    rollout: float = 0.0  # percent 0..100
    kill_switch: bool = False
    description: str | None = None
    updated_at: str | None = None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Experiment":
        vars_in: List[Dict[str, Any]] = d.get("variations", []) or []
        variations = [Variation(v.get("name"), float(v.get("weight", 0))) for v in vars_in]
        return Experiment(
            name=d.get("name"),
            variations=variations,
            enabled=bool(d.get("enabled", False)),
            rollout=float(d.get("rollout", 0.0)),
            kill_switch=bool(d.get("kill_switch", False)),
            description=d.get("description"),
            updated_at=d.get("updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["variations"] = [asdict(v) for v in self.variations]
        return d

    def total_weight(self) -> float:
        return sum(max(0.0, v.weight) for v in self.variations)

    def variation_names(self) -> List[str]:
        return [v.name for v in self.variations]


def pick_variation(variations: List[Variation], user_id: str, exp_name: str) -> Tuple[Optional[str], float]:
    total = sum(max(0.0, v.weight) for v in variations)
    if total <= 0:
        return None, 0.0
    b = stable_bucket("exp", exp_name, str(user_id)) * total
    cumulative = 0.0
    for v in variations:
        w = max(0.0, v.weight)
        cumulative += w
        if b < cumulative:
            return v.name, b / total
    # Fallback
    return variations[-1].name, 1.0


def assign_experiment(experiment: Experiment, user_id: str) -> Dict[str, Any]:
    # Global kill switch overrides
    if GLOBAL_KILL_SWITCH:
        return {
            "experiment": experiment.name,
            "user_id": user_id,
            "in_experiment": False,
            "variant": None,
            "reason": "global_kill_switch",
            "bucket": None,
            "rollout": experiment.rollout,
            "kill_switch": True,
            "enabled": experiment.enabled,
            "timestamp": now_iso(),
        }

    # Experiment-level kill switch
    if experiment.kill_switch:
        return {
            "experiment": experiment.name,
            "user_id": user_id,
            "in_experiment": False,
            "variant": None,
            "reason": "kill_switch",
            "bucket": None,
            "rollout": experiment.rollout,
            "kill_switch": True,
            "enabled": experiment.enabled,
            "timestamp": now_iso(),
        }

    if not experiment.enabled:
        return {
            "experiment": experiment.name,
            "user_id": user_id,
            "in_experiment": False,
            "variant": None,
            "reason": "disabled",
            "bucket": None,
            "rollout": experiment.rollout,
            "kill_switch": False,
            "enabled": experiment.enabled,
            "timestamp": now_iso(),
        }

    # Rollout gate
    rollout_bucket = stable_bucket("exp-rollout", experiment.name, str(user_id))
    threshold = (experiment.rollout or 0.0) / 100.0
    if rollout_bucket >= threshold:
        # Outside experiment rollout; if a control variant exists, return it as non-exposed
        control = next((v.name for v in experiment.variations if v.name.lower() == "control"), None)
        return {
            "experiment": experiment.name,
            "user_id": user_id,
            "in_experiment": False,
            "variant": control,
            "reason": "rollout_holdout",
            "bucket": rollout_bucket,
            "rollout": experiment.rollout,
            "kill_switch": False,
            "enabled": experiment.enabled,
            "timestamp": now_iso(),
        }

    # Pick variation deterministically
    variant, var_bucket = pick_variation(experiment.variations, user_id, experiment.name)
    return {
        "experiment": experiment.name,
        "user_id": user_id,
        "in_experiment": True,
        "variant": variant,
        "reason": "assigned",
        "bucket": var_bucket,
        "rollout": experiment.rollout,
        "kill_switch": False,
        "enabled": experiment.enabled,
        "timestamp": now_iso(),
    }

