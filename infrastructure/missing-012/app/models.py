from datetime import datetime, time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from .extensions import db


def utcnow():
    return datetime.utcnow()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    push_token = db.Column(db.String(255), nullable=True)
    timezone = db.Column(db.String(64), nullable=False, default="UTC")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    preferences = db.relationship(
        "NotificationPreferences",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class NotificationPreferences(db.Model):
    __tablename__ = "notification_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    # Channel toggles
    email_enabled = db.Column(db.Boolean, default=True, nullable=False)
    sms_enabled = db.Column(db.Boolean, default=False, nullable=False)
    push_enabled = db.Column(db.Boolean, default=True, nullable=False)

    # Frequency: immediate, daily, weekly (string for portability)
    frequency = db.Column(db.String(16), default="immediate", nullable=False)

    # Digest options
    digest_enabled = db.Column(db.Boolean, default=True, nullable=False)
    digest_time_local = db.Column(db.Time, default=time(9, 0), nullable=True)  # 09:00 local
    digest_weekday = db.Column(db.Integer, nullable=True)  # 0=Mon .. 6=Sun, used if weekly

    # Category-level overrides (JSON/JSONB)
    # Example structure:
    # {
    #   "marketing": {"email": true, "sms": false, "push": true, "digest": true},
    #   "security":  {"email": true, "sms": true,  "push": true, "digest": false}
    # }
    categories = db.Column(JSONB().with_variant(JSON, "sqlite"), default=dict)

    last_digest_sent_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="preferences")


class NotificationEvent(db.Model):
    __tablename__ = "notification_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category = db.Column(db.String(64), nullable=False)
    message = db.Column(db.Text, nullable=False)

    # Which channels are relevant for this event (e.g., ["email", "push"]) - optional
    channels = db.Column(JSONB().with_variant(JSON, "sqlite"), default=list)

    in_digest = db.Column(db.Boolean, default=False, nullable=False)
    delivered = db.Column(db.Boolean, default=False, nullable=False)
    delivered_channels = db.Column(JSONB().with_variant(JSON, "sqlite"), default=list)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    delivered_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User")

