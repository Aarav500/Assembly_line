from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Translation(Base):
    __tablename__ = "translations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    language: Mapped[str] = mapped_column(String(16), index=True)
    namespace: Mapped[str] = mapped_column(String(64), index=True, default="common")
    key: Mapped[str] = mapped_column(String(512), index=True)
    value: Mapped[str] = mapped_column(String(8192), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("language", "namespace", "key", name="uq_lang_ns_key"),
        Index("ix_lang_ns", "language", "namespace"),
    )

