from datetime import datetime
import json
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()


class Alert(Base):
    __tablename__ = 'alerts'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    source = Column(String(128), index=True)
    service = Column(String(128), index=True)
    severity = Column(String(32), index=True)
    category = Column(String(64), index=True)
    message = Column(Text)
    metadata = Column(Text, nullable=True)
    noise_score = Column(Float, nullable=True)
    is_noise = Column(Boolean, nullable=True, index=True)
    incident_id = Column(Integer, ForeignKey('incidents.id'), nullable=True, index=True)

    incident = relationship('Incident', back_populates='alerts')

    def metadata_dict(self):
        try:
            return json.loads(self.metadata) if self.metadata else {}
        except Exception:
            return {}


Index('idx_alerts_core', Alert.source, Alert.service, Alert.severity, Alert.category)


class Incident(Base):
    __tablename__ = 'incidents'
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    size = Column(Integer, default=0)
    severity = Column(String(32), default='unknown')
    summary = Column(String(256), default='')

    alerts = relationship('Alert', back_populates='incident')


Index('idx_incidents_updated', Incident.updated_at)


def init_db(url: str):
    engine = create_engine(url, echo=False, future=True)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)

