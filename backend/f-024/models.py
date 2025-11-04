from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import json
from db import Base


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    type = Column(String(32), nullable=False, index=True)  # visit | signup | purchase
    user_id = Column(String(255), nullable=True, index=True)
    amount = Column(Float, nullable=True)  # for purchase
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "user_id": self.user_id,
            "amount": self.amount,
            "created_at": (self.created_at.isoformat() + "Z") if self.created_at else None,
        }


class AlertRule(Base):
    __tablename__ = "alert_rules"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    metric = Column(String(64), nullable=False)  # revenue | conversion_rate | signups
    comparator = Column(String(8), nullable=False)  # gt | lt | gte | lte | eq | neq
    threshold = Column(Float, nullable=False)
    window_minutes = Column(Integer, nullable=False, default=60)
    cool_down_minutes = Column(Integer, nullable=False, default=60)
    is_active = Column(Boolean, default=True, nullable=False)
    channels_json = Column(Text, nullable=False, default='[]')
    last_triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    alerts = relationship("Alert", back_populates="rule")

    @staticmethod
    def serialize_channels(channels):
        try:
            return json.dumps(channels)
        except Exception:
            return '[]'

    @staticmethod
    def deserialize_channels(channels_json):
        try:
            channels = json.loads(channels_json or '[]')
            if not isinstance(channels, list):
                return []
            return channels
        except Exception:
            return []

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "metric": self.metric,
            "comparator": self.comparator,
            "threshold": self.threshold,
            "window_minutes": self.window_minutes,
            "cool_down_minutes": self.cool_down_minutes,
            "is_active": self.is_active,
            "channels": self.deserialize_channels(self.channels_json),
            "last_triggered_at": (self.last_triggered_at.isoformat() + "Z") if self.last_triggered_at else None,
            "created_at": (self.created_at.isoformat() + "Z") if self.created_at else None,
        }


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    message = Column(Text, nullable=False)
    delivered_channels_json = Column(Text, nullable=False, default='[]')
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    rule = relationship("AlertRule", back_populates="alerts")

    @staticmethod
    def serialize_delivered(channels):
        try:
            return json.dumps(channels)
        except Exception:
            return '[]'

    @staticmethod
    def deserialize_delivered(channels_json):
        try:
            channels = json.loads(channels_json or '[]')
            if not isinstance(channels, list):
                return []
            return channels
        except Exception:
            return []

    def to_dict(self):
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "metric_value": self.metric_value,
            "message": self.message,
            "delivered_channels": self.deserialize_delivered(self.delivered_channels_json),
            "triggered_at": (self.triggered_at.isoformat() + "Z") if self.triggered_at else None,
            "rule": {
                "id": self.rule.id,
                "name": self.rule.name,
                "metric": self.rule.metric,
                "comparator": self.rule.comparator,
                "threshold": self.rule.threshold,
                "window_minutes": self.rule.window_minutes,
            } if self.rule else None,
        }

