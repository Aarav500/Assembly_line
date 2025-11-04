from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class Secret:
    id: str
    name: str
    versions: Dict[int, str] = field(default_factory=dict)
    latest_version: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0

@dataclass
class Lease:
    id: str
    secret_id: str
    version: int
    created_at: float
    ttl: int
    max_ttl: int
    revoked_at: Optional[float] = None
    planned_revocation_at: Optional[float] = None

    def is_expired(self, now_ts: float) -> bool:
        return self.created_at + self.ttl <= now_ts

    def is_active(self, now_ts: float) -> bool:
        return not self.revoked_at and not self.is_expired(now_ts)

