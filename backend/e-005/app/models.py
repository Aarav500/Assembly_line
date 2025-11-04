from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func


db = SQLAlchemy()


class Policy(db.Model):
    __tablename__ = 'policies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    repository_pattern = db.Column(db.String(512), nullable=False)

    keep_last = db.Column(db.Integer, nullable=True)  # retain last N tags by created
    max_age_days = db.Column(db.Integer, nullable=True)  # delete if older than N days

    keep_tags_regex = db.Column(db.String(512), nullable=True)
    exclude_tags_regex = db.Column(db.String(512), nullable=True)
    protected_tags = db.Column(db.String(1024), nullable=True)  # comma-separated specific tags

    dry_run = db.Column(db.Boolean, default=True, nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)

    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'repository_pattern': self.repository_pattern,
            'keep_last': self.keep_last,
            'max_age_days': self.max_age_days,
            'keep_tags_regex': self.keep_tags_regex,
            'exclude_tags_regex': self.exclude_tags_regex,
            'protected_tags': self.protected_tags,
            'dry_run': self.dry_run,
            'enabled': self.enabled,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() + 'Z',
            'updated_at': self.updated_at.isoformat() + 'Z',
        }


class DeletionLog(db.Model):
    __tablename__ = 'deletion_logs'

    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey('policies.id', ondelete='SET NULL'), nullable=True)

    repository = db.Column(db.String(512), nullable=False)
    tag = db.Column(db.String(256), nullable=True)
    digest = db.Column(db.String(256), nullable=True)

    action = db.Column(db.String(32), nullable=False)  # delete | skip
    reason = db.Column(db.String(1024), nullable=True)
    success = db.Column(db.Boolean, default=False, nullable=False)
    dry_run = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'policy_id': self.policy_id,
            'repository': self.repository,
            'tag': self.tag,
            'digest': self.digest,
            'action': self.action,
            'reason': self.reason,
            'success': self.success,
            'dry_run': self.dry_run,
            'created_at': self.created_at.isoformat() + 'Z',
        }

