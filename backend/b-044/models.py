from datetime import datetime, date
from typing import List
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint

db = SQLAlchemy()

RISK_STATES = [
    "identified",
    "assessed",
    "planned",
    "in_progress",
    "mitigated",
    "accepted",
    "closed",
]

RISK_TRANSITIONS = {
    "identified": ["assessed", "accepted", "closed"],
    "assessed": ["planned", "accepted", "closed"],
    "planned": ["in_progress", "accepted", "closed"],
    "in_progress": ["mitigated", "accepted", "closed"],
    "mitigated": ["closed", "in_progress"],
    "accepted": ["closed"],
    "closed": [],
}

MITIGATION_STATUSES = ["planned", "in_progress", "done", "cancelled"]
MITIGATION_TRANSITIONS = {
    "planned": ["in_progress", "cancelled"],
    "in_progress": ["done", "cancelled"],
    "done": ["in_progress"],
    "cancelled": [],
}

class Idea(db.Model):
    __tablename__ = "ideas"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    risks = db.relationship("Risk", backref="idea", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "risk_count": len(self.risks),
        }

class Risk(db.Model):
    __tablename__ = "risks"
    id = db.Column(db.Integer, primary_key=True)
    idea_id = db.Column(db.Integer, db.ForeignKey("ideas.id"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    owner = db.Column(db.String(120), nullable=True)

    severity = db.Column(db.Integer, nullable=False, default=3)
    likelihood = db.Column(db.Integer, nullable=False, default=3)

    status = db.Column(db.String(32), nullable=False, default="identified")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    mitigations = db.relationship("Mitigation", backref="risk", lazy=True, cascade="all, delete-orphan")
    events = db.relationship("RiskEventLog", backref="risk", lazy=True, cascade="all, delete-orphan", order_by="RiskEventLog.timestamp.desc()")

    __table_args__ = (
        CheckConstraint("severity >= 1 AND severity <= 5", name="ck_risk_severity_range"),
        CheckConstraint("likelihood >= 1 AND likelihood <= 5", name="ck_risk_likelihood_range"),
    )

    @property
    def score(self) -> int:
        return int(self.severity) * int(self.likelihood)

    @property
    def allowed_transitions(self) -> List[str]:
        return RISK_TRANSITIONS.get(self.status, [])

    def transition(self, to_state: str, actor: str = "system", note: str = None):
        to_state = (to_state or "").strip().lower()
        if to_state not in RISK_STATES:
            raise ValueError(f"Invalid risk state: {to_state}")
        if to_state not in self.allowed_transitions:
            raise ValueError(f"Transition from {self.status} to {to_state} not allowed")
        from_state = self.status
        self.status = to_state
        self.updated_at = datetime.utcnow()
        evt = RiskEventLog(risk=self, action="transition", from_state=from_state, to_state=to_state, actor=actor, note=note)
        db.session.add(evt)

    def ensure_state(self, desired_state: str, actor: str = "system", note: str = None):
        if self.status == desired_state:
            return
        if desired_state in self.allowed_transitions:
            self.transition(desired_state, actor=actor, note=note)

    def to_dict(self, include_related: bool = False):
        data = {
            "id": self.id,
            "idea_id": self.idea_id,
            "title": self.title,
            "description": self.description,
            "owner": self.owner,
            "severity": self.severity,
            "likelihood": self.likelihood,
            "score": self.score,
            "status": self.status,
            "allowed_transitions": self.allowed_transitions,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_related:
            data["mitigations"] = [m.to_dict() for m in self.mitigations]
            data["events"] = [e.to_dict() for e in self.events]
        return data

    def recompute_status_from_mitigations(self):
        statuses = [m.status for m in self.mitigations]
        # If any mitigation in progress, try to set risk to in_progress
        if any(s == "in_progress" for s in statuses):
            if "in_progress" in self.allowed_transitions:
                self.transition("in_progress", actor="system", note="Auto-update from mitigation in progress")
            return
        # If all mitigations are done or cancelled and there is at least one mitigation
        if statuses and all(s in ("done", "cancelled") for s in statuses):
            if "mitigated" in self.allowed_transitions:
                self.transition("mitigated", actor="system", note="Auto-update: all mitigations completed/cancelled")
            return
        # If at least one planned and current is earlier, try to move to planned
        if any(s == "planned" for s in statuses):
            if "planned" in self.allowed_transitions:
                self.transition("planned", actor="system", note="Auto-update from planned mitigation")

class Mitigation(db.Model):
    __tablename__ = "mitigations"
    id = db.Column(db.Integer, primary_key=True)
    risk_id = db.Column(db.Integer, db.ForeignKey("risks.id"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    owner = db.Column(db.String(120), nullable=True)

    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="planned")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def allowed_transitions(self) -> List[str]:
        return MITIGATION_TRANSITIONS.get(self.status, [])

    def transition(self, to_status: str):
        to_status = (to_status or "").strip().lower()
        if to_status not in MITIGATION_STATUSES:
            raise ValueError(f"Invalid mitigation status: {to_status}")
        if to_status not in self.allowed_transitions:
            raise ValueError(f"Transition from {self.status} to {to_status} not allowed")
        self.status = to_status
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        return {
            "id": self.id,
            "risk_id": self.risk_id,
            "title": self.title,
            "description": self.description,
            "owner": self.owner,
            "due_date": self.due_date.isoformat() if isinstance(self.due_date, date) else None,
            "status": self.status,
            "allowed_transitions": self.allowed_transitions,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class RiskEventLog(db.Model):
    __tablename__ = "risk_events"
    id = db.Column(db.Integer, primary_key=True)
    risk_id = db.Column(db.Integer, db.ForeignKey("risks.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    action = db.Column(db.String(64), nullable=False)
    from_state = db.Column(db.String(32), nullable=True)
    to_state = db.Column(db.String(32), nullable=True)
    actor = db.Column(db.String(120), nullable=True)
    note = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "risk_id": self.risk_id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "actor": self.actor,
            "note": self.note,
        }

