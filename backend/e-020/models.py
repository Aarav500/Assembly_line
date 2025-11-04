from datetime import datetime, timezone
from database import db


def utcnow():
    return datetime.now(timezone.utc)


class Tenant(db.Model):
    __tablename__ = 'tenants'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    projects = db.relationship('Project', backref='tenant', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
        }


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    resources = db.relationship('Resource', backref='project', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'name', name='uq_project_tenant_name'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'tenant_id': self.tenant_id,
            'created_at': self.created_at.isoformat(),
        }


class Resource(db.Model):
    __tablename__ = 'resources'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    size = db.Column(db.String(50), nullable=True)
    base_rate = db.Column(db.Float, nullable=True)  # USD per hour
    active = db.Column(db.Boolean, default=True, nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    tenant = db.relationship('Tenant', backref=db.backref('resources', lazy=True))
    tags = db.relationship('ResourceTag', cascade='all, delete-orphan', backref='resource', lazy=True)

    __table_args__ = (
        db.Index('ix_resource_tenant', 'tenant_id'),
        db.Index('ix_resource_project', 'project_id'),
    )

    def tags_dict(self):
        return {t.key: t.value for t in self.tags}

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'size': self.size,
            'base_rate': self.base_rate,
            'active': self.active,
            'tenant_id': self.tenant_id,
            'project_id': self.project_id,
            'tags': self.tags_dict(),
            'created_at': self.created_at.isoformat(),
        }


class ResourceTag(db.Model):
    __tablename__ = 'resource_tags'
    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resources.id', ondelete='CASCADE'), nullable=False)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(255), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('resource_id', 'key', name='uq_resource_tag_key'),
        db.Index('ix_tag_key', 'key'),
        db.Index('ix_tag_kv', 'key', 'value'),
    )

    def to_dict(self):
        return {'key': self.key, 'value': self.value}


class CostRecord(db.Model):
    __tablename__ = 'cost_records'
    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resources.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    start_hour = db.Column(db.DateTime, nullable=False)  # UTC hour start
    hours = db.Column(db.Integer, default=1, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='USD', nullable=False)
    computed_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    resource = db.relationship('Resource')
    project = db.relationship('Project')
    tenant = db.relationship('Tenant')

    __table_args__ = (
        db.UniqueConstraint('resource_id', 'start_hour', name='uq_cost_resource_hour'),
        db.Index('ix_cost_tenant_hour', 'tenant_id', 'start_hour'),
        db.Index('ix_cost_project_hour', 'project_id', 'start_hour'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'resource_id': self.resource_id,
            'project_id': self.project_id,
            'tenant_id': self.tenant_id,
            'start_hour': self.start_hour.replace(tzinfo=timezone.utc).isoformat(),
            'hours': self.hours,
            'amount': round(self.amount, 6),
            'currency': self.currency,
            'computed_at': self.computed_at.replace(tzinfo=timezone.utc).isoformat(),
        }

