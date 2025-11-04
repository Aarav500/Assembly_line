import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(255), unique=True, nullable=True, index=True)
    first_seen_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    sessions = relationship("Session", back_populates="user")
    events = relationship("Event", back_populates="user")


class Identity(Base):
    __tablename__ = "identities"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    anonymous_id = Column(String(255), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    first_seen_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("anonymous_id", "user_id", name="uq_identity_anon_user"),
    )


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    anonymous_id = Column(String(255), nullable=True, index=True)
    started_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    user_agent = Column(Text, nullable=True)
    ip = Column(String(64), nullable=True)
    referrer = Column(Text, nullable=True)
    utm = Column(JSONB, nullable=True)

    user = relationship("User", back_populates="sessions")
    events = relationship("Event", back_populates="session")

    __table_args__ = (
        Index("ix_sessions_user_started", "user_id", "started_at"),
        Index("ix_sessions_anon_started", "anonymous_id", "started_at"),
    )


class Event(Base):
    __tablename__ = "events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    anonymous_id = Column(String(255), nullable=True, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    properties = Column(JSONB, nullable=True)
    event_time = Column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    user = relationship("User", back_populates="events")
    session = relationship("Session", back_populates="events")

    __table_args__ = (
        Index("ix_events_name_time", "name", "event_time"),
        Index("ix_events_user_time", "user_id", "event_time"),
        Index("ix_events_anon_time", "anonymous_id", "event_time"),
        Index("ix_events_properties_gin", "properties", postgresql_using="gin"),
    )

