from __future__ import annotations
import enum
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


class DeploymentStatus(enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PROMOTED = "PROMOTED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class Event:
    ts: float
    level: str
    msg: str


@dataclass
class CanaryConfig:
    initial_weight: int = 5
    step_weight: int = 10
    interval_sec: int = 60
    max_steps: int = 20

    # Metrics/SLO policy
    max_error_rate: Optional[float] = 0.01  # 1%
    max_latency_p95_ms: Optional[float] = 500.0
    min_availability: Optional[float] = 0.995
    max_cpu_utilization: Optional[float] = 0.85

    # Evaluation window/requirements
    sample_window_sec: int = 60
    min_samples: int = 3
    min_requests: int = 100

    # Failure handling
    rollback_on_failure: bool = True
    max_consecutive_failures: int = 1

    @staticmethod
    def from_dict(strategy: Dict[str, Any], policy: Dict[str, Any]) -> "CanaryConfig":
        cfg = CanaryConfig()
        # Strategy fields
        for k in ["initial_weight", "step_weight", "interval_sec", "max_steps"]:
            if k in strategy:
                setattr(cfg, k, strategy[k])
        # Policy fields
        mapping = {
            "max_error_rate": "max_error_rate",
            "max_latency_p95_ms": "max_latency_p95_ms",
            "min_availability": "min_availability",
            "max_cpu_utilization": "max_cpu_utilization",
            "sample_window_sec": "sample_window_sec",
            "min_samples": "min_samples",
            "min_requests": "min_requests",
            "rollback_on_failure": "rollback_on_failure",
            "max_consecutive_failures": "max_consecutive_failures",
        }
        for src, attr in mapping.items():
            if src in policy:
                setattr(cfg, attr, policy[src])
        # Bounds
        cfg.initial_weight = int(max(0, min(100, cfg.initial_weight)))
        cfg.step_weight = int(max(1, min(100, cfg.step_weight)))
        cfg.interval_sec = int(max(5, cfg.interval_sec))
        cfg.sample_window_sec = int(max(5, cfg.sample_window_sec))
        cfg.min_samples = int(max(1, cfg.min_samples))
        cfg.min_requests = int(max(0, cfg.min_requests))
        cfg.max_steps = int(max(1, cfg.max_steps))
        if cfg.max_consecutive_failures < 1:
            cfg.max_consecutive_failures = 1
        return cfg


@dataclass
class CanaryDeployment:
    id: str
    service_name: str
    new_version: str
    baseline_version: str
    config: CanaryConfig
    status: DeploymentStatus = DeploymentStatus.PENDING
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())

    # runtime state
    current_weight: int = 0
    current_step: int = 0
    last_step_started_at: Optional[float] = None
    last_metrics_at: Optional[float] = None
    last_aggregates: Optional[Dict[str, float]] = None
    fail_count: int = 0
    completed_at: Optional[float] = None

    # aux
    metrics_window: Any = None  # set at runtime
    history: List[Event] = field(default_factory=list)

    def to_dict(self, summary: bool = False) -> Dict[str, Any]:
        base = {
            "id": self.id,
            "service_name": self.service_name,
            "new_version": self.new_version,
            "baseline_version": self.baseline_version,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_weight": self.current_weight,
            "current_step": self.current_step,
            "last_step_started_at": self.last_step_started_at,
            "last_metrics_at": self.last_metrics_at,
            "fail_count": self.fail_count,
            "completed_at": self.completed_at,
        }
        if not summary:
            base["config"] = asdict(self.config)
            base["history"] = [asdict(e) for e in self.history[-200:]]
            base["last_aggregates"] = self.last_aggregates
        return base

