from datetime import datetime
from enum import Enum
from sqlalchemy import func
from sqlalchemy.types import JSON
from db import db

class Severity(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"

class DigestFrequency(str, Enum):
    immediate = "immediate"  # unused for team
    hourly = "hourly"
    daily = "daily"

class RouteMode(str, Enum):
    immediate = "immediate"
    digest = "digest"

class Channel(str, Enum):
    email = "email"
    slack = "slack"
    webhook = "webhook"

class DeliveryStatus(str, Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"

class DeliveryType(str, Enum):
    single = "single"
    digest = "digest"

class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    timezone = db.Column(db.String(64), default='UTC', nullable=False)
    digest_enabled = db.Column(db.Boolean, default=True, nullable=False)
    digest_frequency = db.Column(db.String(16), default=DigestFrequency.hourly.value, nullable=False)
    digest_hour = db.Column(db.Integer, nullable=True)  # for daily
    digest_minute = db.Column(db.Integer, default=0, nullable=False)  # for hourly/daily
    last_digest_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    routes = db.relationship('Route', backref='team', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'timezone': self.timezone,
            'digest_enabled': self.digest_enabled,
            'digest_frequency': self.digest_frequency,
            'digest_hour': self.digest_hour,
            'digest_minute': self.digest_minute,
            'last_digest_at': self.last_digest_at.isoformat() if self.last_digest_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

class Route(db.Model):
    __tablename__ = 'routes'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    channel = db.Column(db.String(16), nullable=False)
    target = db.Column(db.String(512), nullable=False)
    mode = db.Column(db.String(16), default=RouteMode.immediate.value, nullable=False)
    filters = db.Column(JSON, nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'team_id': self.team_id,
            'channel': self.channel,
            'target': self.target,
            'mode': self.mode,
            'filters': self.filters or {},
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=True)
    severity = db.Column(db.String(16), default=Severity.info.value, nullable=False)
    event_type = db.Column(db.String(64), nullable=True)
    tags = db.Column(JSON, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'team_id': self.team_id,
            'title': self.title,
            'message': self.message,
            'severity': self.severity,
            'event_type': self.event_type,
            'tags': self.tags or [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class Delivery(db.Model):
    __tablename__ = 'deliveries'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id'), nullable=True)
    delivery_type = db.Column(db.String(16), default=DeliveryType.single.value, nullable=False)
    status = db.Column(db.String(16), default=DeliveryStatus.pending.value, nullable=False)
    channel = db.Column(db.String(16), nullable=False)
    target = db.Column(db.String(512), nullable=False)
    payload = db.Column(JSON, nullable=True)
    scheduled_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'team_id': self.team_id,
            'route_id': self.route_id,
            'delivery_type': self.delivery_type,
            'status': self.status,
            'channel': self.channel,
            'target': self.target,
            'payload': self.payload,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'error': self.error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

