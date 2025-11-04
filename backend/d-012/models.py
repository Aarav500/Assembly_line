import json
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Text, func
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = 'sqlite:///app.db'

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={'check_same_thread': False}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class IncidentTicket(Base):
    __tablename__ = 'incident_tickets'

    id = Column(Integer, primary_key=True)
    service = Column(String(255), nullable=False)
    attempted_version = Column(String(255), nullable=False)
    previous_version = Column(String(255), nullable=True)
    rollback_version = Column(String(255), nullable=True)
    status = Column(String(64), default='open', nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    snapshot = Column(Text, nullable=False)  # JSON string

    def to_dict(self):
        return {
            'id': self.id,
            'service': self.service,
            'attempted_version': self.attempted_version,
            'previous_version': self.previous_version,
            'rollback_version': self.rollback_version,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'snapshot': json.loads(self.snapshot) if self.snapshot else None,
        }


class ServiceState(Base):
    __tablename__ = 'service_states'

    service = Column(String(255), primary_key=True)
    current_version = Column(String(255), nullable=True)
    last_good_version = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self):
        return {
            'service': self.service,
            'current_version': self.current_version,
            'last_good_version': self.last_good_version,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


def init_db():
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()

