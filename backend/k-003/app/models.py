from __future__ import annotations
from datetime import datetime, time
from typing import Optional

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum
from sqlalchemy.orm import validates

from .extensions import db


class Schedule(db.Model):
    __tablename__ = "schedules"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)

    task_type = db.Column(Enum("maintenance", "retraining", name="task_type"), nullable=False)

    timezone = db.Column(db.String(64), nullable=False, default="UTC")

    # e.g., "mon,tue,wed,thu,fri" or "mon-sun" or "*"
    days_of_week = db.Column(db.String(64), nullable=False, default="mon-sun")

    start_time = db.Column(db.Time, nullable=False)

    # Maintenance window duration (minutes). Required for maintenance, ignored for retraining.
    duration_minutes = db.Column(db.Integer, nullable=True)

    enabled = db.Column(db.Boolean, nullable=False, default=True)

    last_run_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @validates("days_of_week")
    def validate_dow(self, key, value):
        if value is None:
            raise ValueError("days_of_week is required")
        v = value.strip().lower()
        if v == "*":
            return "mon,tue,wed,thu,fri,sat,sun"
        # Basic validation; APScheduler will further parse this
        allowed = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        parts = []
        for token in v.split(","):
            token = token.strip()
            if not token:
                continue
            if "-" in token:
                a, b = token.split("-", 1)
                a = a.strip(); b = b.strip()
                if a not in allowed or b not in allowed:
                    raise ValueError("Invalid day range in days_of_week")
                parts.append(f"{a}-{b}")
            else:
                if token not in allowed:
                    raise ValueError("Invalid day in days_of_week")
                parts.append(token)
        if not parts:
            raise ValueError("days_of_week cannot be empty")
        return ",".join(parts)

    @validates("start_time")
    def validate_start_time(self, key, value: time):
        if not isinstance(value, time):
            raise ValueError("start_time must be a time object")
        return value

    @validates("task_type")
    def validate_task_type(self, key, value):
        if value not in ("maintenance", "retraining"):
            raise ValueError("task_type must be 'maintenance' or 'retraining'")
        return value

    @validates("duration_minutes")
    def validate_duration(self, key, value):
        if self.task_type == "maintenance":
            if value is None or value <= 0:
                raise ValueError("duration_minutes must be > 0 for maintenance windows")
        return value

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "task_type": self.task_type,
            "timezone": self.timezone,
            "days_of_week": self.days_of_week,
            "start_time": self.start_time.strftime("%H:%M"),
            "duration_minutes": self.duration_minutes,
            "enabled": self.enabled,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }

