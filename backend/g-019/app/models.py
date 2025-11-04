from datetime import datetime
import json
from sqlalchemy import UniqueConstraint
from . import db

class Tenant(db.Model):
    __tablename__ = 'tenants'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    users = db.relationship('User', backref='tenant', lazy=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "created_at": self.created_at.isoformat()}


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    role = db.Column(db.String(64), nullable=False, default='member')
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    api_keys = db.relationship('ApiKey', backref='user', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat(),
        }


class ApiKey(db.Model):
    __tablename__ = 'api_keys'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(128), unique=True, index=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    tenant = db.relationship('Tenant', backref='api_keys', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "key": self.key,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat(),
        }


class ModelRegistry(db.Model):
    __tablename__ = 'models'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "created_at": self.created_at.isoformat()}


class TenantModelPolicy(db.Model):
    __tablename__ = 'tenant_model_policies'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    model_name = db.Column(db.String(120), nullable=False)
    allowed = db.Column(db.Boolean, default=True, nullable=False)
    roles_allowed_json = db.Column(db.Text, nullable=True)  # JSON array of role strings
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = db.relationship('Tenant', backref='model_policies', lazy=True)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'model_name', name='uq_tenant_model'),
    )

    def roles_allowed(self):
        if not self.roles_allowed_json:
            return None
        try:
            return json.loads(self.roles_allowed_json)
        except Exception:
            return None

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "model_name": self.model_name,
            "allowed": self.allowed,
            "roles_allowed": self.roles_allowed(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TenantQuota(db.Model):
    __tablename__ = 'tenant_quotas'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    period = db.Column(db.String(32), nullable=False)  # 'daily' or 'monthly'
    max_calls = db.Column(db.Integer, nullable=False)
    used_calls = db.Column(db.Integer, default=0, nullable=False)
    window_start = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = db.relationship('Tenant', backref='quotas', lazy=True)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'period', name='uq_tenant_period'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "period": self.period,
            "max_calls": self.max_calls,
            "used_calls": self.used_calls,
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UsageLog(db.Model):
    __tablename__ = 'usage_logs'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    model_name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    tenant = db.relationship('Tenant', backref='usage_logs', lazy=True)
    user = db.relationship('User', backref='usage_logs', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "model_name": self.model_name,
            "created_at": self.created_at.isoformat(),
        }


def init_db():
    db.create_all()

