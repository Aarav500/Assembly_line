from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from db import Base

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    events = relationship("AuditEvent", back_populates="project", cascade="all, delete-orphan")

class AuditEvent(Base):
    __tablename__ = 'audit_events'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    action_type = Column(String(64), nullable=False)
    user_id = Column(String(128), nullable=True)
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(256), nullable=True)
    metadata = Column(Text, nullable=False, default='{}')
    created_at = Column(DateTime, nullable=False)
    prev_hash = Column(String(64), nullable=False)
    event_hash = Column(String(64), nullable=False)

    project = relationship("Project", back_populates="events")

    __table_args__ = (
        Index('ix_audit_events_project_id_created_at', 'project_id', 'created_at'),
        Index('ix_audit_events_project_id_id', 'project_id', 'id'),
        Index('ix_audit_events_event_hash', 'event_hash'),
    )

    def to_dict(self):
        from utils import dt_to_iso
        return {
            'id': self.id,
            'project_id': self.project_id,
            'action_type': self.action_type,
            'user_id': self.user_id,
            'ip': self.ip,
            'user_agent': self.user_agent,
            'metadata': self.metadata,
            'created_at': dt_to_iso(self.created_at),
            'prev_hash': self.prev_hash,
            'event_hash': self.event_hash,
        }

