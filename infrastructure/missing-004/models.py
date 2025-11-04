import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer, JSON, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class EmailMessage(Base):
    __tablename__ = "email_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    to_email = Column(String(320), nullable=False)
    subject = Column(String(255), nullable=False)
    template_name = Column(String(255), nullable=False)
    template_context = Column(JSON, nullable=True)

    provider = Column(String(50), nullable=False, default="sendgrid")
    status = Column(String(50), nullable=False, default="queued")
    error = Column(Text, nullable=True)

    message_id = Column(String(255), nullable=True)  # provider message id

    tags = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)

    attempt_count = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(DateTime, nullable=True)

    bounce_reason = Column(Text, nullable=True)

    events = relationship("EventLog", back_populates="email", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "to": self.to_email,
            "subject": self.subject,
            "template_name": self.template_name,
            "template_context": self.template_context,
            "provider": self.provider,
            "status": self.status,
            "error": self.error,
            "message_id": self.message_id,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "clicked_at": self.clicked_at.isoformat() if self.clicked_at else None,
            "attempt_count": self.attempt_count,
            "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None,
            "bounce_reason": self.bounce_reason,
        }


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email_id = Column(String(36), ForeignKey("email_messages.id"), nullable=True)
    provider = Column(String(50), nullable=False)
    provider_event_id = Column(String(255), nullable=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    email = relationship("EmailMessage", back_populates="events")


class Unsubscribe(Base):
    __tablename__ = "unsubscribes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(320), nullable=False, unique=True)
    reason = Column(String(255), nullable=True)
    source = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

