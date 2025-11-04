from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import relationship
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from . import db
from .utils import isoformat_utc


class Release(db.Model):
    __tablename__ = 'releases'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(255), nullable=False, index=True)
    version = db.Column(String(64), nullable=False, index=True)
    description = db.Column(Text, nullable=True)
    created_at = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    stages = relationship('Stage', back_populates='release', cascade='all, delete-orphan', order_by='Stage.start_at')

    def to_dict(self, include_stages: bool = True) -> Dict[str, Any]:
        data = {
            'id': self.id,
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'created_at': isoformat_utc(self.created_at),
            'updated_at': isoformat_utc(self.updated_at),
        }
        if include_stages:
            data['stages'] = [s.to_dict() for s in self.stages]
        return data


class Stage(db.Model):
    __tablename__ = 'stages'
    id = db.Column(Integer, primary_key=True)
    release_id = db.Column(Integer, ForeignKey('releases.id', ondelete='CASCADE'), nullable=False, index=True)

    name = db.Column(String(255), nullable=False)
    target = db.Column(String(255), nullable=True)  # e.g., environment name or ring
    percentage = db.Column(Integer, nullable=True)  # 0..100 optional for cohort rollouts
    ci_job_name = db.Column(String(255), nullable=True)

    start_at = db.Column(DateTime, nullable=False, index=True)
    end_at = db.Column(DateTime, nullable=True, index=True)

    status = db.Column(String(32), default='pending', nullable=False, index=True)  # pending|triggered|completed|failed|skipped
    last_triggered_at = db.Column(DateTime, nullable=True)
    logs_url = db.Column(Text, nullable=True)

    created_at = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    release = relationship('Release', back_populates='stages')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'release_id': self.release_id,
            'name': self.name,
            'target': self.target,
            'percentage': self.percentage,
            'ci_job_name': self.ci_job_name,
            'start_at': isoformat_utc(self.start_at),
            'end_at': isoformat_utc(self.end_at) if self.end_at else None,
            'status': self.status,
            'last_triggered_at': isoformat_utc(self.last_triggered_at) if self.last_triggered_at else None,
            'logs_url': self.logs_url,
            'created_at': isoformat_utc(self.created_at),
            'updated_at': isoformat_utc(self.updated_at),
        }

    def is_active_time(self, now: datetime) -> bool:
        if self.start_at and now < self.start_at:
            return False
        if self.end_at and now >= self.end_at:
            return False
        return True

    def within_trigger_window(self, now: datetime, window_minutes: int) -> bool:
        delta = now - self.start_at
        # Only trigger once, within [start_at, start_at + window]
        return delta.total_seconds() >= 0 and delta.total_seconds() <= window_minutes * 60

