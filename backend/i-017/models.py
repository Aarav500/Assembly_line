import uuid
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func


db = SQLAlchemy()


class ConsentPolicy(db.Model):
    __tablename__ = 'consent_policies'
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.Integer, nullable=False, unique=True)
    text = db.Column(db.Text, nullable=False)
    effective_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    purpose = db.Column(db.String(64), nullable=False)
    payload_encrypted = db.Column(db.Text, nullable=False)
    # Optional field-level encryption key id if you implement rotation later
    key_id = db.Column(db.String(64), nullable=True)

    # Consent snapshot
    consent_version = db.Column(db.Integer, nullable=False)
    consent_timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)


class ContactEmail(db.Model):
    __tablename__ = 'contact_emails'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.String(36), db.ForeignKey('submissions.id', ondelete='CASCADE'), index=True, nullable=False)
    email_encrypted = db.Column(db.Text, nullable=False)


class AuditEvent(db.Model):
    __tablename__ = 'audit_events'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.String(36), db.ForeignKey('submissions.id', ondelete='SET NULL'), index=True, nullable=True)
    event_type = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def ensure_default_policy():
    # Seed a default policy if none exists
    if not ConsentPolicy.query.first():
        policy = ConsentPolicy(version=1, text=(
            'We practice data minimization. We only collect the minimal data necessary for the stated purpose, '
            'store it encrypted, retain it for a limited time, and delete it automatically after expiration.'
        ))
        db.session.add(policy)
        db.session.commit()

