from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime


db = SQLAlchemy()


class SnapshotSchedule(db.Model):
    __tablename__ = 'snapshot_schedules'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    source_path = db.Column(db.String(1024), nullable=False)
    cron = db.Column(db.String(255), nullable=True)
    interval_minutes = db.Column(db.Integer, nullable=True)
    retention = db.Column(db.Integer, nullable=False, default=7)
    snapshot_format = db.Column(db.String(32), nullable=False, default='tar.gz')
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    last_run_at = db.Column(db.DateTime, nullable=True)
    next_run_at = db.Column(db.DateTime, nullable=True)
    tags = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    snapshots = db.relationship('Snapshot', backref='schedule', lazy=True)

    def to_dict(self, include_snapshots=False):
        data = {
            'id': self.id,
            'name': self.name,
            'source_path': self.source_path,
            'cron': self.cron,
            'interval_minutes': self.interval_minutes,
            'retention': self.retention,
            'snapshot_format': self.snapshot_format,
            'enabled': self.enabled,
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
            'next_run_at': self.next_run_at.isoformat() if self.next_run_at else None,
            'tags': self.tags or {},
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
        if include_snapshots:
            data['snapshots'] = [s.to_dict() for s in self.snapshots]
        return data


class Snapshot(db.Model):
    __tablename__ = 'snapshots'
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('snapshot_schedules.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(32), nullable=False, default='PENDING')
    path = db.Column(db.String(2048), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)
    checksum = db.Column(db.String(128), nullable=True)
    log_text = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'created_at': self.created_at.isoformat(),
            'status': self.status,
            'path': self.path,
            'size_bytes': self.size_bytes,
            'checksum': self.checksum,
            'log_text': self.log_text,
        }


class Runbook(db.Model):
    __tablename__ = 'runbooks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    steps_json = db.Column(db.JSON, nullable=False, default=list)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    drills = db.relationship('Drill', backref='runbook', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'steps': self.steps_json or [],
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class Drill(db.Model):
    __tablename__ = 'drills'
    id = db.Column(db.Integer, primary_key=True)
    runbook_id = db.Column(db.Integer, db.ForeignKey('runbooks.id'), nullable=False)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(32), nullable=False, default='PENDING')
    log_text = db.Column(db.Text, nullable=True)
    result_json = db.Column(db.JSON, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'runbook_id': self.runbook_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'status': self.status,
            'log_text': self.log_text,
            'result': self.result_json or {},
        }


class DrillSchedule(db.Model):
    __tablename__ = 'drill_schedules'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    runbook_id = db.Column(db.Integer, db.ForeignKey('runbooks.id'), nullable=False)
    cron = db.Column(db.String(255), nullable=True)
    interval_minutes = db.Column(db.Integer, nullable=True)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    last_run_at = db.Column(db.DateTime, nullable=True)
    next_run_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'runbook_id': self.runbook_id,
            'cron': self.cron,
            'interval_minutes': self.interval_minutes,
            'enabled': self.enabled,
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
            'next_run_at': self.next_run_at.isoformat() if self.next_run_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

