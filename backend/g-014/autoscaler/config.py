import os
import yaml
from dataclasses import dataclass, asdict


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "y", "on")


@dataclass
class Config:
    loop_tick_seconds: float = 2.0

    # Autoscaling policy
    scale_up_sensitivity: float = 1.0  # multiplier on desired replicas
    scale_down_cooldown_seconds: float = 30.0
    max_scale_step: int = 50

    # Spot policy
    default_spot_fraction_cap: float = 0.8  # max share on spot per deployment
    global_spot_eviction_rate_per_minute: float = 0.05  # probability per spot node per minute

    # Node/GPU config
    gpu_per_node: int = 1
    node_startup_seconds: float = 8.0

    # Scheduler
    reschedule_on_preemption: bool = True

    # Pool names
    on_demand_pool_name: str = "on-demand"
    spot_pool_name: str = "spot"

    # Metrics
    metrics_namespace: str = "model_autoscaler"

    def to_dict(self):
        return asdict(self)

    def update_from_dict(self, data: dict):
        for k, v in data.items():
            if hasattr(self, k):
                setattr(self, k, v)


def load_config(path: str) -> Config:
    cfg = Config(
        loop_tick_seconds=_env_float("LOOP_TICK_SECONDS", 2.0),
        scale_up_sensitivity=_env_float("SCALE_UP_SENSITIVITY", 1.0),
        scale_down_cooldown_seconds=_env_float("SCALE_DOWN_COOLDOWN_SECONDS", 30.0),
        max_scale_step=_env_int("MAX_SCALE_STEP", 50),
        default_spot_fraction_cap=_env_float("DEFAULT_SPOT_FRACTION_CAP", 0.8),
        global_spot_eviction_rate_per_minute=_env_float("GLOBAL_SPOT_EVICTION_RATE_PER_MINUTE", 0.05),
        gpu_per_node=_env_int("GPU_PER_NODE", 1),
        node_startup_seconds=_env_float("NODE_STARTUP_SECONDS", 8.0),
        reschedule_on_preemption=_env_bool("RESCHEDULE_ON_PREEMPTION", True),
        on_demand_pool_name=os.getenv("ON_DEMAND_POOL_NAME", "on-demand"),
        spot_pool_name=os.getenv("SPOT_POOL_NAME", "spot"),
        metrics_namespace=os.getenv("METRICS_NAMESPACE", "model_autoscaler"),
    )
    try:
        if path and os.path.exists(path):
            with open(path, 'r') as f:
                data = yaml.safe_load(f) or {}
                cfg.update_from_dict(data)
    except Exception:
        pass
    return cfg

