from datetime import datetime
from typing import Optional
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.sqlite import JSON as SqliteJSON
from . import db


class Domain(db.Model):
    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    provider_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    provider_config: Mapped[Optional[dict]] = mapped_column(SqliteJSON, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="new")  # new, ready, error
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    cert_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chain_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fullchain_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    not_after: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "provider_name": self.provider_name,
            "provider_config": self.provider_config,
            "status": self.status,
            "last_error": self.last_error,
            "cert_path": self.cert_path,
            "key_path": self.key_path,
            "chain_path": self.chain_path,
            "fullchain_path": self.fullchain_path,
            "not_after": self.not_after.isoformat() if self.not_after else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

