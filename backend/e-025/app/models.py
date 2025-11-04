import uuid
import json
from datetime import datetime
from sqlalchemy.orm import validates
from .db import db


def generate_uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.utcnow()


class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(120), unique=True, nullable=False)
    api_key = db.Column(db.String(64), unique=True, nullable=False)
    quota_dev = db.Column(db.Integer, nullable=False, default=5)
    quota_stage = db.Column(db.Integer, nullable=False, default=3)
    quota_prod = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    environments = db.relationship('Environment', backref='team', lazy=True)


class Environment(db.Model):
    __tablename__ = 'environments'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(120), nullable=False)
    env_type = db.Column(db.String(16), nullable=False)  # dev, stage, prod
    status = db.Column(db.String(32), nullable=False, default='requested')
    region = db.Column(db.String(64), nullable=True)
    config_text = db.Column(db.Text, nullable=False, default='{}')
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    team_id = db.Column(db.String(36), db.ForeignKey('teams.id'), nullable=False)

    tasks = db.relationship('ProvisionTask', backref='environment', lazy=True)

    @property
    def config(self):
        try:
            return json.loads(self.config_text or '{}')
        except Exception:
            return {}

    @config.setter
    def config(self, value):
        if value is None:
            self.config_text = '{}'
        elif isinstance(value, str):
            self.config_text = value
        else:
            self.config_text = json.dumps(value)

    @validates('env_type')
    def validate_env_type(self, key, value):
        allowed = {'dev', 'stage', 'prod'}
        if value not in allowed:
            raise ValueError('env_type must be one of dev, stage, prod')
        return value

    @validates('status')
    def validate_status(self, key, value):
        allowed = {
            'requested', 'provisioning', 'active', 'failed',
            'deprovisioning', 'deleted'
        }
        if value not in allowed:
            raise ValueError('invalid status')
        return value


class ProvisionTask(db.Model):
    __tablename__ = 'provision_tasks'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    environment_id = db.Column(db.String(36), db.ForeignKey('environments.id'), nullable=False)
    action = db.Column(db.String(32), nullable=False)  # provision, deprovision, update
    status = db.Column(db.String(32), nullable=False, default='pending')  # pending, running, succeeded, failed
    logs = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class AuditEvent(db.Model):
    __tablename__ = 'audit_events'
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    team_id = db.Column(db.String(36), db.ForeignKey('teams.id'), nullable=False)
    environment_id = db.Column(db.String(36), db.ForeignKey('environments.id'), nullable=True)
    action = db.Column(db.String(64), nullable=False)
    actor = db.Column(db.String(128), nullable=False)
    details_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    @property
    def details(self):
        try:
            return json.loads(self.details_text or '{}')
        except Exception:
            return {}

    @details.setter
    def details(self, value):
        if value is None:
            self.details_text = '{}'
        elif isinstance(value, str):
            self.details_text = value
        else:
            self.details_text = json.dumps(value)

