from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index


db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Runbook(TimestampMixin, db.Model):
    __tablename__ = "runbooks"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    url = db.Column(db.String(1024), nullable=False)
    description = db.Column(db.Text, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class EscalationPolicy(TimestampMixin, db.Model):
    __tablename__ = "escalation_policies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    # List of levels [{ delay_seconds|delay_minutes, targets: ["email", ...] }]
    levels = db.Column(db.JSON, nullable=False, default=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "levels": self.levels,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Alert(TimestampMixin, db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    severity = db.Column(db.String(50), nullable=False, default="info")

    policy_id = db.Column(db.Integer, db.ForeignKey("escalation_policies.id"), nullable=False)
    runbook_id = db.Column(db.Integer, db.ForeignKey("runbooks.id"), nullable=False)

    policy = db.relationship("EscalationPolicy", lazy="joined")
    runbook = db.relationship("Runbook", lazy="joined")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "severity": self.severity,
            "policy_id": self.policy_id,
            "runbook_id": self.runbook_id,
            "policy_name": self.policy.name if self.policy else None,
            "runbook_url": self.runbook.url if self.runbook else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Incident(TimestampMixin, db.Model):
    __tablename__ = "incidents"

    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.Integer, db.ForeignKey("alerts.id"), nullable=False)

    status = db.Column(db.String(32), nullable=False, default="open")  # open, acknowledged, resolved
    current_level = db.Column(db.Integer, nullable=True)  # -1 before first escalation

    last_escalated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    acknowledged_at = db.Column(db.DateTime(timezone=True), nullable=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Snapshots
    runbook_url = db.Column(db.String(1024), nullable=True)
    policy_name = db.Column(db.String(255), nullable=True)
    policy_levels = db.Column(db.JSON, nullable=False, default=list)
    alert_snapshot = db.Column(db.JSON, nullable=True)

    alert = db.relationship("Alert", lazy="joined")

    notifications = db.relationship("IncidentNotification", backref="incident", lazy="select", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_incidents_status", "status"),
        Index("ix_incidents_alert_id", "alert_id"),
    )

    def to_dict(self, include_notifications: bool = False) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "status": self.status,
            "current_level": self.current_level,
            "alert_id": self.alert_id,
            "alert": self.alert_snapshot or (self.alert.to_dict() if self.alert else None),
            "runbook_url": self.runbook_url,
            "policy_name": self.policy_name,
            "policy_levels": self.policy_levels,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_escalated_at": self.last_escalated_at.isoformat() if self.last_escalated_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
        if include_notifications:
            data["notifications"] = [n.to_dict() for n in self.notifications]
        return data


class IncidentNotification(TimestampMixin, db.Model):
    __tablename__ = "incident_notifications"

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("incidents.id"), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    target = db.Column(db.String(255), nullable=False)
    notified_via = db.Column(db.String(64), nullable=False, default="simulated")
    sent_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    status = db.Column(db.String(32), nullable=False, default="sent")  # sent/failed
    message = db.Column(db.Text, nullable=True)

    __table_args__ = (
        Index("ix_notifs_incident_id", "incident_id"),
        Index("ix_notifs_level", "level"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "level": self.level,
            "target": self.target,
            "notified_via": self.notified_via,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "status": self.status,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

