from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime, timezone


class ProposalStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


@dataclass
class Change:
    field: str
    from_value: Any
    to_value: Any
    op: str  # add|update|remove (remove represented as to_value=None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "from": self.from_value,
            "to": self.to_value,
            "op": self.op,
        }


@dataclass
class Proposal:
    id: str
    resource: str
    target_id: str
    status: ProposalStatus
    changes: List[Change] = field(default_factory=list)
    agent_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    original_snapshot: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "resource": self.resource,
            "target_id": self.target_id,
            "status": self.status.value,
            "changes": [c.to_dict() for c in self.changes],
            "agent_id": self.agent_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "original_snapshot": self.original_snapshot,
        }

    @staticmethod
    def new(resource: str, target_id: str, changes: List[Change], agent_id: Optional[str], original_snapshot: Optional[Dict[str, Any]]):
        return Proposal(
            id=str(uuid4()),
            resource=resource,
            target_id=target_id,
            status=ProposalStatus.PROPOSED,
            changes=changes,
            agent_id=agent_id,
            original_snapshot=original_snapshot,
        )

