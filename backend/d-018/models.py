from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import uuid


def _coerce_str_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]


@dataclass
class Runner:
    id: str
    name: str
    provider: str
    cost_per_minute: float
    cpu: int
    memory_mb: int
    performance_score: float = 1.0
    labels: List[str] = field(default_factory=list)
    online: bool = True
    capacity: int = 1
    running_jobs: int = 0
    queue_time_estimate: float = 0.0
    preemptible: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Runner":
        # Validate required fields
        required = ["name", "provider", "cost_per_minute", "cpu", "memory_mb"]
        for k in required:
            if k not in d:
                raise ValueError(f"Missing required field: {k}")
        rid = d.get("id") or str(uuid.uuid4())
        return Runner(
            id=rid,
            name=str(d["name"]),
            provider=str(d["provider"]),
            cost_per_minute=float(d["cost_per_minute"]),
            cpu=int(d["cpu"]),
            memory_mb=int(d["memory_mb"]),
            performance_score=float(d.get("performance_score", 1.0)),
            labels=_coerce_str_list(d.get("labels")),
            online=bool(d.get("online", True)),
            capacity=int(d.get("capacity", 1)),
            running_jobs=int(d.get("running_jobs", 0)),
            queue_time_estimate=float(d.get("queue_time_estimate", 0.0)),
            preemptible=bool(d.get("preemptible", False)),
            meta=d.get("meta", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class JobRequest:
    estimated_minutes: float
    cpu_req: int = 1
    mem_req_mb: int = 1024
    required_labels: List[str] = field(default_factory=list)
    allow_preemptible: bool = False
    priority: str = "normal"  # low, normal, high
    deadline_minutes: Optional[float] = None
    budget_cap: Optional[float] = None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "JobRequest":
        if "estimated_minutes" not in d:
            raise ValueError("Missing required field: estimated_minutes")
        priority = str(d.get("priority", "normal")).lower()
        if priority not in ("low", "normal", "high"):
            raise ValueError("priority must be one of: low, normal, high")
        deadline = d.get("deadline_minutes")
        deadline_v = float(deadline) if deadline is not None else None
        budget = d.get("budget_cap")
        budget_v = float(budget) if budget is not None else None
        return JobRequest(
            estimated_minutes=float(d["estimated_minutes"]),
            cpu_req=int(d.get("cpu_req", 1)),
            mem_req_mb=int(d.get("mem_req_mb", 1024)),
            required_labels=_coerce_str_list(d.get("required_labels")),
            allow_preemptible=bool(d.get("allow_preemptible", False)),
            priority=priority,
            deadline_minutes=deadline_v,
            budget_cap=budget_v,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

