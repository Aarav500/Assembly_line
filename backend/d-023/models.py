from datetime import datetime
from sqlalchemy.orm import validates
from sqlalchemy import UniqueConstraint
from database import db


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')  # admin, approver, user
    api_key = db.Column(db.String(64), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'active': self.active,
            'created_at': self.created_at.isoformat() + 'Z'
        }


class Stage(db.Model):
    __tablename__ = 'stages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    position = db.Column(db.Integer, nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    gates = db.relationship('Gate', backref='stage', cascade='all, delete-orphan', lazy=True)

    def to_dict(self, with_gates=False):
        data = {
            'id': self.id,
            'name': self.name,
            'position': self.position,
            'created_at': self.created_at.isoformat() + 'Z'
        }
        if with_gates:
            data['gates'] = [g.to_dict(include_allowed=True) for g in self.gates]
        return data


class Gate(db.Model):
    __tablename__ = 'gates'
    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey('stages.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    required_approvals = db.Column(db.Integer, nullable=False, default=1)
    allow_roles = db.Column(db.String(255), nullable=True)  # comma-separated roles
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    allowed_users = db.relationship('GateAllowedUser', backref='gate', cascade='all, delete-orphan', lazy=True)

    def allowed_role_list(self):
        if not self.allow_roles:
            return []
        return [r.strip() for r in self.allow_roles.split(',') if r.strip()]

    def to_dict(self, include_allowed=False):
        data = {
            'id': self.id,
            'stage_id': self.stage_id,
            'name': self.name,
            'description': self.description,
            'required_approvals': self.required_approvals,
            'allow_roles': self.allowed_role_list(),
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() + 'Z'
        }
        if include_allowed:
            data['allowed_users'] = [au.user_id for au in self.allowed_users]
        return data


class GateAllowedUser(db.Model):
    __tablename__ = 'gate_allowed_users'
    id = db.Column(db.Integer, primary_key=True)
    gate_id = db.Column(db.Integer, db.ForeignKey('gates.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    __table_args__ = (
        UniqueConstraint('gate_id', 'user_id', name='uq_gate_user'),
    )


class Deployment(db.Model):
    __tablename__ = 'deployments'
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='pending')  # pending, in_progress, blocked, completed
    current_stage_id = db.Column(db.Integer, db.ForeignKey('stages.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    current_stage = db.relationship('Stage', foreign_keys=[current_stage_id], lazy=True)
    approvals = db.relationship('GateApproval', backref='deployment', cascade='all, delete-orphan', lazy=True)

    def to_dict(self, include_details=False):
        data = {
            'id': self.id,
            'version': self.version,
            'description': self.description,
            'status': self.status,
            'current_stage_id': self.current_stage_id,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() + 'Z',
            'updated_at': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
        }
        if include_details:
            data['current_stage'] = self.current_stage.to_dict(with_gates=True) if self.current_stage else None
            data['approvals'] = [a.to_dict() for a in self.approvals]
        return data


class GateApproval(db.Model):
    __tablename__ = 'gate_approvals'
    id = db.Column(db.Integer, primary_key=True)
    deployment_id = db.Column(db.Integer, db.ForeignKey('deployments.id'), nullable=False)
    gate_id = db.Column(db.Integer, db.ForeignKey('gates.id'), nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    decision = db.Column(db.String(20), nullable=False)  # approved or rejected
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    gate = db.relationship('Gate', foreign_keys=[gate_id], lazy=True)

    __table_args__ = (
        UniqueConstraint('deployment_id', 'gate_id', 'approver_id', name='uq_approval_unique'),
    )

    @validates('decision')
    def validate_decision(self, key, value):
        if value not in ('approved', 'rejected'):
            raise ValueError('decision must be approved or rejected')
        return value

    def to_dict(self):
        return {
            'id': self.id,
            'deployment_id': self.deployment_id,
            'gate_id': self.gate_id,
            'approver_id': self.approver_id,
            'decision': self.decision,
            'comment': self.comment,
            'created_at': self.created_at.isoformat() + 'Z',
            'updated_at': self.updated_at.isoformat() + 'Z' if self.updated_at else None
        }


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    entity_type = db.Column(db.String(120), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'actor_id': self.actor_id,
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'details': self.details,
            'created_at': self.created_at.isoformat() + 'Z'
        }

