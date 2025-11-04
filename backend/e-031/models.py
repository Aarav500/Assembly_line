import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.orm import relationship


db = SQLAlchemy()


def gen_uuid():
    return str(uuid.uuid4())


class MachineCredential(db.Model):
    __tablename__ = 'machine_credentials'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(255), nullable=False)
    access_key = db.Column(db.String(128), unique=True, nullable=False)
    status = db.Column(db.String(32), nullable=False, default='active')  # active, disabled
    rotation_interval_seconds = db.Column(db.Integer, nullable=False)
    last_rotated_at = db.Column(db.DateTime, nullable=True)
    compromised_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    active_version_id = db.Column(db.String(36), db.ForeignKey('credential_versions.id'), nullable=True)

    active_version = relationship('CredentialVersion', foreign_keys=[active_version_id])
    versions = relationship('CredentialVersion', back_populates='credential', order_by='CredentialVersion.version.asc()')


class CredentialVersion(db.Model):
    __tablename__ = 'credential_versions'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    machine_credential_id = db.Column(db.String(36), db.ForeignKey('machine_credentials.id'), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    secret_encrypted = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    reason = db.Column(db.String(255), nullable=True)

    credential = relationship('MachineCredential', back_populates='versions')


class AuditEvent(db.Model):
    __tablename__ = 'audit_events'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    event_type = db.Column(db.String(64), nullable=False)
    credential_id = db.Column(db.String(36), db.ForeignKey('machine_credentials.id'), nullable=True)
    version_id = db.Column(db.String(36), db.ForeignKey('credential_versions.id'), nullable=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

