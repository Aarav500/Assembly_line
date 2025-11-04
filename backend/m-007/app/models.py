from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, Index
from datetime import datetime


db = SQLAlchemy()


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow(), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow(), nullable=False)


class Owner(TimestampMixin, db.Model):
    __tablename__ = 'owners'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    email = db.Column(db.String(255), nullable=False)

    tests = db.relationship('TestCase', backref='owner', lazy=True)
    rules = db.relationship('OwnershipRule', backref='owner', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'created_at': self.created_at.isoformat() + 'Z',
            'updated_at': self.updated_at.isoformat() + 'Z',
        }


class OwnershipRule(TimestampMixin, db.Model):
    __tablename__ = 'ownership_rules'
    id = db.Column(db.Integer, primary_key=True)
    pattern = db.Column(db.String(255), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id'), nullable=False)
    scope = db.Column(db.String(32), nullable=False, default='path')  # 'path' or 'name'
    priority = db.Column(db.Integer, nullable=False, default=100)  # lower wins

    def to_dict(self):
        return {
            'id': self.id,
            'pattern': self.pattern,
            'scope': self.scope,
            'priority': self.priority,
            'owner': self.owner.to_dict() if self.owner else None,
            'created_at': self.created_at.isoformat() + 'Z',
            'updated_at': self.updated_at.isoformat() + 'Z',
        }


class TestCase(TimestampMixin, db.Model):
    __tablename__ = 'tests'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    path = db.Column(db.String(512), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id'), nullable=True)
    flakiness_score = db.Column(db.Float, nullable=True)
    last_analyzed_at = db.Column(db.DateTime, nullable=True)

    runs = db.relationship('TestRun', backref='test', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'path': self.path,
            'owner': self.owner.to_dict() if self.owner else None,
            'flakiness_score': self.flakiness_score,
            'last_analyzed_at': self.last_analyzed_at.isoformat() + 'Z' if self.last_analyzed_at else None,
            'created_at': self.created_at.isoformat() + 'Z',
            'updated_at': self.updated_at.isoformat() + 'Z',
        }


class TestRun(TimestampMixin, db.Model):
    __tablename__ = 'test_runs'
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('tests.id'), nullable=False, index=True)
    status = db.Column(db.String(16), nullable=False)  # 'pass' or 'fail'
    duration_ms = db.Column(db.Integer, nullable=True)
    build_id = db.Column(db.String(128), nullable=True)
    commit_sha = db.Column(db.String(64), nullable=True)
    executed_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow(), index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'test_id': self.test_id,
            'status': self.status,
            'duration_ms': self.duration_ms,
            'build_id': self.build_id,
            'commit_sha': self.commit_sha,
            'executed_at': self.executed_at.isoformat() + 'Z',
            'created_at': self.created_at.isoformat() + 'Z',
        }


class RetestJob(TimestampMixin, db.Model):
    __tablename__ = 'retest_jobs'
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('tests.id'), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id'), nullable=True)
    status = db.Column(db.String(16), nullable=False, default='pending')  # 'pending','running','completed','failed'
    reason = db.Column(db.String(255), nullable=True)
    scheduled_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow(), index=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)

    test = db.relationship('TestCase', backref='retest_jobs', lazy=True)
    owner = db.relationship('Owner', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'test': self.test.to_dict() if self.test else None,
            'owner': self.owner.to_dict() if self.owner else None,
            'status': self.status,
            'reason': self.reason,
            'scheduled_at': self.scheduled_at.isoformat() + 'Z' if self.scheduled_at else None,
            'started_at': self.started_at.isoformat() + 'Z' if self.started_at else None,
            'completed_at': self.completed_at.isoformat() + 'Z' if self.completed_at else None,
            'attempts': self.attempts,
            'created_at': self.created_at.isoformat() + 'Z',
            'updated_at': self.updated_at.isoformat() + 'Z',
        }


Index('ix_test_runs_test_id_executed_at', TestRun.test_id, TestRun.executed_at.desc())
Index('ix_retest_jobs_test_id_status', RetestJob.test_id, RetestJob.status)

