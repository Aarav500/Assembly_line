from datetime import datetime
from secrets import token_urlsafe
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint


db = SQLAlchemy()


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Organization(db.Model, TimestampMixin):
    __tablename__ = 'organizations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    api_key = db.Column(db.String(128), nullable=False, unique=True, index=True)

    agents = db.relationship('Agent', backref='organization', lazy=True)
    resources = db.relationship('Resource', backref='organization', lazy=True)

    @staticmethod
    def generate_api_key() -> str:
        return token_urlsafe(48)


class Agent(db.Model, TimestampMixin):
    __tablename__ = 'agents'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    config = db.Column(db.JSON, nullable=True)

    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint('name', 'org_id', name='uq_agent_name_org'),
    )


class Resource(db.Model, TimestampMixin):
    __tablename__ = 'resources'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)

    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint('title', 'org_id', name='uq_resource_title_org'),
    )


