from sqlalchemy import Column, String, Integer, DateTime, Numeric, Text
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.types import JSON
from database import Base
from datetime import datetime


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(String, primary_key=True)
    created_at = Column(DateTime, nullable=False, index=True)

    workflow_id = Column(String, index=True, nullable=False)
    run_id = Column(String, index=True)

    provider = Column(String, index=True)
    model = Column(String, index=True)

    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0, index=True)

    prompt_cost_usd = Column(Numeric(18, 10), default=0)
    completion_cost_usd = Column(Numeric(18, 10), default=0)
    total_cost_usd = Column(Numeric(18, 10), default=0, index=True)

    input_chars = Column(Integer)
    output_chars = Column(Integer)

    metadata = Column(JSON().with_variant(SQLITE_JSON, 'sqlite'))

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "workflow_id": self.workflow_id,
            "run_id": self.run_id,
            "provider": self.provider,
            "model": self.model,
            "prompt_tokens": int(self.prompt_tokens or 0),
            "completion_tokens": int(self.completion_tokens or 0),
            "total_tokens": int(self.total_tokens or 0),
            "prompt_cost_usd": float(self.prompt_cost_usd or 0),
            "completion_cost_usd": float(self.completion_cost_usd or 0),
            "total_cost_usd": float(self.total_cost_usd or 0),
            "input_chars": int(self.input_chars) if self.input_chars is not None else None,
            "output_chars": int(self.output_chars) if self.output_chars is not None else None,
            "metadata": self.metadata,
        }

    def to_row(self):
        d = self.to_dict()
        # Ensure metadata serialized string for CSV
        md = d.get("metadata")
        if md is not None:
            try:
                d["metadata"] = json.dumps(md, ensure_ascii=False)
            except Exception:
                d["metadata"] = str(md)
        else:
            d["metadata"] = ""
        return d


class Pricing(Base):
    __tablename__ = "pricing"

    id = Column(String, primary_key=True)
    provider = Column(String, index=True, nullable=False)
    model = Column(String, index=True, nullable=False)
    input_per_1k_usd = Column(Numeric(18, 10), nullable=False)
    output_per_1k_usd = Column(Numeric(18, 10), nullable=False)
    currency = Column(String, default="USD")
    updated_at = Column(DateTime, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "provider": self.provider,
            "model": self.model,
            "input_per_1k_usd": float(self.input_per_1k_usd),
            "output_per_1k_usd": float(self.output_per_1k_usd),
            "currency": self.currency,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }


# Local import to satisfy to_row JSON dumps
import json  # noqa: E402

