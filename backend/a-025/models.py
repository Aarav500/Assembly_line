from datetime import datetime
from sqlalchemy import UniqueConstraint
from database import db


def now_utc():
    return datetime.utcnow()


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    current_state = db.Column(db.JSON, nullable=False, default=dict)
    current_version = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_utc, onupdate=now_utc)

    snapshots = db.relationship('Snapshot', backref='project', lazy=True, cascade='all, delete-orphan')
    checkpoints = db.relationship('Checkpoint', backref='project', lazy=True, cascade='all, delete-orphan')
    audits = db.relationship('AuditLog', backref='project', lazy=True, cascade='all, delete-orphan')

    def to_dict(self, include_state=True):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'current_state': self.current_state if include_state else None,
            'current_version': self.current_version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Snapshot(db.Model):
    __tablename__ = 'snapshots'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    label = db.Column(db.String(255), nullable=True)
    data = db.Column(db.JSON, nullable=False, default=dict)
    version = db.Column(db.Integer, nullable=False)
    is_bookmark = db.Column(db.Boolean, nullable=False, default=False)
    is_read_only = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    __table_args__ = (
        UniqueConstraint('project_id', 'label', 'is_bookmark', name='uq_project_bookmark_label', sqlite_where=(db.text('is_bookmark = 1'))),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'label': self.label,
            'data': self.data,
            'version': self.version,
            'is_bookmark': self.is_bookmark,
            'is_read_only': self.is_read_only,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Checkpoint(db.Model):
    __tablename__ = 'checkpoints'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    label = db.Column(db.String(255), nullable=True)
    data = db.Column(db.JSON, nullable=False, default=dict)
    index = db.Column(db.Integer, nullable=False)  # sequential index within a project
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'label': self.label,
            'data': self.data,
            'index': self.index,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    action = db.Column(db.String(64), nullable=False)
    meta = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'action': self.action,
            'meta': self.meta,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

