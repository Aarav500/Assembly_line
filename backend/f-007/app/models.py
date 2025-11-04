from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, unique=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    slack_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "slack_id": self.slack_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    start_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    shift_length_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=720)

    next_handoff_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_participant_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    notify_slack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    slack_channel: Mapped[str | None] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    participants = relationship("ScheduleParticipant", cascade="all, delete-orphan", back_populates="schedule", order_by="ScheduleParticipant.order_index")
    handoff_history = relationship("HandoffHistory", cascade="all, delete-orphan", back_populates="schedule")
    overrides = relationship("ScheduleOverride", cascade="all, delete-orphan", back_populates="schedule")

    def to_dict(self, include_participants=False):
        data = {
            "id": self.id,
            "name": self.name,
            "timezone": self.timezone,
            "start_time_utc": self.start_time_utc.isoformat() if self.start_time_utc else None,
            "shift_length_minutes": self.shift_length_minutes,
            "next_handoff_at_utc": self.next_handoff_at_utc.isoformat() if self.next_handoff_at_utc else None,
            "current_participant_index": self.current_participant_index,
            "notify_slack": self.notify_slack,
            "notify_email": self.notify_email,
            "slack_channel": self.slack_channel,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_participants:
            data["participants"] = [p.to_dict() for p in self.participants]
        return data


class ScheduleParticipant(Base):
    __tablename__ = "schedule_participants"
    __table_args__ = (
        UniqueConstraint("schedule_id", "order_index", name="uq_schedule_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    schedule = relationship("Schedule", back_populates="participants")
    user = relationship("User")

    def to_dict(self):
        return {"id": self.id, "schedule_id": self.schedule_id, "user_id": self.user_id, "order_index": self.order_index}


class HandoffHistory(Base):
    __tablename__ = "handoff_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False)
    from_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    to_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    schedule = relationship("Schedule", back_populates="handoff_history")
    from_user = relationship("User", foreign_keys=[from_user_id])
    to_user = relationship("User", foreign_keys=[to_user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "from_user_id": self.from_user_id,
            "to_user_id": self.to_user_id,
            "at_utc": self.at_utc.isoformat() if self.at_utc else None,
            "reason": self.reason,
        }


class ScheduleOverride(Base):
    __tablename__ = "schedule_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    schedule = relationship("Schedule", back_populates="overrides")
    user = relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "user_id": self.user_id,
            "start_utc": self.start_utc.isoformat() if self.start_utc else None,
            "end_utc": self.end_utc.isoformat() if self.end_utc else None,
            "reason": self.reason,
        }

