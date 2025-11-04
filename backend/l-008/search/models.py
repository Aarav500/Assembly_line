from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime

@dataclass
class Document:
    id: str
    source_type: str  # code | idea | doc | model | other
    title: str
    path: Optional[str]
    tags: List[str]
    content: str
    extra: Dict[str, Any]
    created_at: str

    @staticmethod
    def from_payload(payload: Dict[str, Any]) -> "Document":
        sid = payload.get("id") or str(uuid4())
        st = (payload.get("source_type") or payload.get("type") or "other").lower()
        title = payload.get("title") or (payload.get("path") or "").split("/")[-1] or sid
        path = payload.get("path")
        tags = payload.get("tags") or []
        content = payload.get("content") or ""
        extra = payload.get("extra") or {}
        created_at = payload.get("created_at") or datetime.utcnow().isoformat() + "Z"
        return Document(
            id=sid,
            source_type=st,
            title=title,
            path=path,
            tags=tags,
            content=content,
            extra=extra,
            created_at=created_at,
        )

    def to_dict(self):
        return asdict(self)

