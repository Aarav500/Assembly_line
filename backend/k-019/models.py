import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import JSON


db = SQLAlchemy()


class Agent(db.Model):
    __tablename__ = "agents"

    id = db.Column(db.String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    metadata = db.Column(JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    sla = db.relationship("SLA", backref="agent", uselist=False, cascade="all,delete-orphan")


class SLA(db.Model):
    __tablename__ = "slas"

    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.String(64), db.ForeignKey("agents.id"), nullable=False, unique=True)

    target_uptime = db.Column(db.Float, nullable=False)              # fraction 0..1
    max_error_rate = db.Column(db.Float, nullable=False)             # fraction 0..1
    p95_latency_ms_target = db.Column(db.Integer, nullable=False)
    min_success_rate = db.Column(db.Float, nullable=False)           # fraction 0..1
    max_cost_per_interaction_usd = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class MetricEvent(db.Model):
    __tablename__ = "metric_events"

    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.String(64), db.ForeignKey("agents.id"), nullable=False, index=True)

    ts = db.Column(db.DateTime, nullable=False, index=True, default=datetime.utcnow)

    # Types: interaction, error, downtime, custom
    type = db.Column(db.String(32), nullable=False, default="interaction")

    # Interaction metrics
    duration_ms = db.Column(db.Integer, nullable=True)
    success = db.Column(db.Boolean, nullable=True)
    error_code = db.Column(db.String(128), nullable=True)

    # Token/cost metrics
    input_tokens = db.Column(db.Integer, nullable=True)
    output_tokens = db.Column(db.Integer, nullable=True)
    cost_usd = db.Column(db.Float, nullable=True)

    # Business value
    revenue_usd = db.Column(db.Float, nullable=True)

    # Arbitrary metadata
    metadata = db.Column(JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    agent = db.relationship("Agent", backref=db.backref("events", lazy=True))

    @staticmethod
    def count_by_type(agent_id, start, end, types):
        q = db.session.query(func.count(MetricEvent.id)).filter(
            MetricEvent.agent_id == agent_id,
            MetricEvent.ts >= start,
            MetricEvent.ts <= end,
            MetricEvent.type.in_(types if isinstance(types, (list, tuple, set)) else [types])
        )
        return q.scalar() or 0

