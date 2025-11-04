from __future__ import annotations
from threading import Lock
from typing import Dict, Optional
from .models import Plan


class PlanStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._plans: Dict[str, Plan] = {}

    def save(self, plan: Plan) -> None:
        with self._lock:
            self._plans[plan.plan_id] = plan

    def get(self, plan_id: str) -> Optional[Plan]:
        with self._lock:
            return self._plans.get(plan_id)

    def all(self) -> Dict[str, Plan]:
        with self._lock:
            return dict(self._plans)

