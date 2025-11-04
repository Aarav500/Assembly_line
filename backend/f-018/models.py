from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Date
from sqlalchemy.orm import relationship

from database import Base


class Service(Base):
    __tablename__ = "services"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(String(1000))

    timezone = Column(String(64), default="UTC", nullable=False)

    slo_availability_target = Column(Float, default=0.999)
    slo_latency_ms_p95 = Column(Float, default=300.0)
    slo_error_rate_target = Column(Float, default=0.001)
    slo_window_days = Column(Integer, default=30)

    created_at = Column(DateTime, default=datetime.utcnow)

    measurements = relationship("Measurement", back_populates="service", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="service", cascade="all, delete-orphan")
    reports = relationship("DailyReport", back_populates="service", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "timezone": self.timezone,
            "slo": {
                "availability_target": self.slo_availability_target,
                "latency_ms_p95": self.slo_latency_ms_p95,
                "error_rate_target": self.slo_error_rate_target,
                "window_days": self.slo_window_days,
            },
            "created_at": (self.created_at.isoformat() + "Z") if self.created_at else None,
        }


class Measurement(Base):
    __tablename__ = "measurements"
    id = Column(Integer, primary_key=True)
    service_id = Column(Integer, ForeignKey("services.id"), index=True, nullable=False)

    ts_utc = Column(DateTime, index=True, nullable=False)
    up = Column(Boolean, nullable=True)
    latency_ms = Column(Float, nullable=True)
    errors = Column(Integer, nullable=True)
    requests = Column(Integer, nullable=True)
    source = Column(String(64), default="api")

    service = relationship("Service", back_populates="measurements")

    def to_dict(self):
        return {
            "id": self.id,
            "service_id": self.service_id,
            "ts": self.ts_utc.isoformat() + "Z" if self.ts_utc else None,
            "up": self.up,
            "latency_ms": self.latency_ms,
            "errors": self.errors,
            "requests": self.requests,
            "source": self.source,
        }


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True)
    service_id = Column(Integer, ForeignKey("services.id"), index=True, nullable=False)

    start_utc = Column(DateTime, nullable=False)
    end_utc = Column(DateTime, nullable=True)

    severity = Column(String(32), default="minor")
    cause = Column(String(255), nullable=True)
    description = Column(String(2000), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    service = relationship("Service", back_populates="incidents")

    def to_dict(self):
        return {
            "id": self.id,
            "service_id": self.service_id,
            "start": self.start_utc.isoformat() + "Z" if self.start_utc else None,
            "end": self.end_utc.isoformat() + "Z" if self.end_utc else None,
            "severity": self.severity,
            "cause": self.cause,
            "description": self.description,
            "created_at": (self.created_at.isoformat() + "Z") if self.created_at else None,
        }


class DailyReport(Base):
    __tablename__ = "daily_reports"
    id = Column(Integer, primary_key=True)
    service_id = Column(Integer, ForeignKey("services.id"), index=True, nullable=False)

    date = Column(Date, index=True, nullable=False)
    timezone = Column(String(64), default="UTC", nullable=False)

    availability = Column(Float, nullable=True)
    latency_p95 = Column(Float, nullable=True)
    error_rate = Column(Float, nullable=True)

    slo_availability_met = Column(Boolean, nullable=True)
    slo_latency_met = Column(Boolean, nullable=True)
    slo_error_rate_met = Column(Boolean, nullable=True)
    slo_overall_met = Column(Boolean, nullable=True)

    computed_at = Column(DateTime, default=datetime.utcnow)

    service = relationship("Service", back_populates="reports")

    def to_dict(self):
        return {
            "id": self.id,
            "service_id": self.service_id,
            "date": self.date.isoformat() if isinstance(self.date, date) else str(self.date),
            "timezone": self.timezone,
            "metrics": {
                "availability": self.availability,
                "latency_p95": self.latency_p95,
                "error_rate": self.error_rate,
            },
            "slo_met": {
                "availability": self.slo_availability_met,
                "latency_p95": self.slo_latency_met,
                "error_rate": self.slo_error_rate_met,
                "overall": self.slo_overall_met,
            },
            "computed_at": (self.computed_at.isoformat() + "Z") if self.computed_at else None,
        }

