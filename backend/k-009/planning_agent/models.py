from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + 'Z'


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class ChecklistItem:
    item_id: str
    text: str
    done: bool = False
    mandatory: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "text": self.text,
            "done": self.done,
            "mandatory": self.mandatory,
        }


@dataclass
class Step:
    step_id: str
    name: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    required_resources: Dict[str, List[str]] = field(default_factory=lambda: {"tools": [], "skills": [], "materials": []})
    checklist: List[ChecklistItem] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    estimate_hours: float = 1.0
    status: str = "pending"  # pending, ready, in_progress, done, blocked
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "dependencies": self.dependencies,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "required_resources": self.required_resources,
            "checklist": [c.to_dict() for c in self.checklist],
            "acceptance_criteria": self.acceptance_criteria,
            "estimate_hours": self.estimate_hours,
            "status": self.status,
            "completed_at": self.completed_at,
        }


@dataclass
class ExecutionEvent:
    ts: str
    level: str
    message: str
    step_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "level": self.level,
            "message": self.message,
            "step_id": self.step_id,
        }


@dataclass
class Plan:
    plan_id: str
    goal: str
    context: str
    constraints: List[str]
    preferences: Dict[str, Any]
    created_at: str
    status: str  # draft, approved, executing, halted, completed
    steps: List[Step]
    manifest: Dict[str, Any]
    logs: List[ExecutionEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "context": self.context,
            "constraints": self.constraints,
            "preferences": self.preferences,
            "created_at": self.created_at,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "manifest": self.manifest,
            "logs": [l.to_dict() for l in self.logs],
        }

    def add_log(self, level: str, message: str, step_id: Optional[str] = None):
        self.logs.append(ExecutionEvent(ts=_now_iso(), level=level, message=message, step_id=step_id))


@dataclass
class ChecklistUpdate:
    step_id: str
    updates: List[Dict[str, Any]]


@dataclass
class ChecklistUpdateRequest:
    updates: List[ChecklistUpdate]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ChecklistUpdateRequest':
        updates_raw = data.get('updates')
        if not isinstance(updates_raw, list) or not updates_raw:
            raise ValueError("'updates' must be a non-empty list")
        updates: List[ChecklistUpdate] = []
        for u in updates_raw:
            step_id = u.get('step_id')
            items = u.get('updates')
            if not step_id or not isinstance(items, list):
                raise ValueError("each update must include 'step_id' and 'updates' list")
            updates.append(ChecklistUpdate(step_id=step_id, updates=items))
        return ChecklistUpdateRequest(updates=updates)

