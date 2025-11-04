import uuid
from datetime import datetime
from sqlalchemy.dialects.sqlite import JSON
from .db import db


def _uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.utcnow()


class Asset(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.String, primary_key=True, default=_uuid)
    name = db.Column(db.String, nullable=False)
    type = db.Column(db.String, nullable=False)
    provider = db.Column(db.String, nullable=False)
    region = db.Column(db.String, nullable=True)
    tags = db.Column(JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    findings = db.relationship('Finding', backref='asset', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'provider': self.provider,
            'region': self.region,
            'tags': self.tags or {},
            'created_at': self.created_at.isoformat() + 'Z'
        }


class Rule(db.Model):
    __tablename__ = 'rules'
    id = db.Column(db.String, primary_key=True, default=_uuid)
    key = db.Column(db.String, unique=True, nullable=False)
    title = db.Column(db.String, nullable=False)
    severity = db.Column(db.String, nullable=False)  # Low, Medium, High, Critical
    description = db.Column(db.Text, nullable=True)
    remediation_guidance = db.Column(db.Text, nullable=True)
    service = db.Column(db.String, nullable=True)
    query = db.Column(db.Text, nullable=True)

    findings = db.relationship('Finding', backref='rule', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'title': self.title,
            'severity': self.severity,
            'description': self.description,
            'remediation_guidance': self.remediation_guidance,
            'service': self.service,
            'query': self.query
        }


class Scan(db.Model):
    __tablename__ = 'scans'
    id = db.Column(db.String, primary_key=True, default=_uuid)
    started_at = db.Column(db.DateTime, default=utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    provider = db.Column(db.String, nullable=True)
    status = db.Column(db.String, nullable=False, default='Running')  # Running, Completed, Failed
    asset_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)

    findings = db.relationship('Finding', backref='scan', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'started_at': self.started_at.isoformat() + 'Z',
            'finished_at': self.finished_at.isoformat() + 'Z' if self.finished_at else None,
            'provider': self.provider,
            'status': self.status,
            'asset_count': self.asset_count,
            'created_at': self.created_at.isoformat() + 'Z'
        }


class Finding(db.Model):
    __tablename__ = 'findings'
    id = db.Column(db.String, primary_key=True, default=_uuid)
    scan_id = db.Column(db.String, db.ForeignKey('scans.id'), nullable=False)
    asset_id = db.Column(db.String, db.ForeignKey('assets.id'), nullable=False)
    rule_id = db.Column(db.String, db.ForeignKey('rules.id'), nullable=False)

    status = db.Column(db.String, nullable=False, default='Open')  # Open, Suppressed, Resolved
    state = db.Column(db.String, nullable=False, default='Fail')  # Pass, Fail
    severity = db.Column(db.String, nullable=False, default='Medium')
    observed_at = db.Column(db.DateTime, default=utcnow)

    details = db.Column(JSON, nullable=True)
    evidence = db.Column(db.Text, nullable=True)
    rationale = db.Column(db.Text, nullable=True)

    rem_actions = db.relationship('RemediationAction', backref='finding', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'scan_id': self.scan_id,
            'asset_id': self.asset_id,
            'rule_id': self.rule_id,
            'status': self.status,
            'state': self.state,
            'severity': self.severity,
            'observed_at': self.observed_at.isoformat() + 'Z' if self.observed_at else None,
            'details': self.details or {},
            'evidence': self.evidence,
            'rationale': self.rationale
        }


class Remediation(db.Model):
    __tablename__ = 'remediations'
    id = db.Column(db.String, primary_key=True, default=_uuid)
    created_at = db.Column(db.DateTime, default=utcnow)
    status = db.Column(db.String, nullable=False, default='Planned')  # Planned, InProgress, Completed, Cancelled
    owner = db.Column(db.String, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    summary = db.Column(db.String, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    actions = db.relationship('RemediationAction', backref='remediation', lazy=True, cascade="all, delete-orphan")

    def to_dict(self, include_actions=True):
        data = {
            'id': self.id,
            'created_at': self.created_at.isoformat() + 'Z',
            'status': self.status,
            'owner': self.owner,
            'due_date': self.due_date.isoformat() + 'Z' if self.due_date else None,
            'summary': self.summary,
            'notes': self.notes,
        }
        if include_actions:
            data['actions'] = [a.to_dict() for a in self.actions]
        return data


class RemediationAction(db.Model):
    __tablename__ = 'remediation_actions'
    id = db.Column(db.String, primary_key=True, default=_uuid)
    remediation_id = db.Column(db.String, db.ForeignKey('remediations.id'), nullable=False)
    finding_id = db.Column(db.String, db.ForeignKey('findings.id'), nullable=False)

    action = db.Column(db.Text, nullable=True)
    status = db.Column(db.String, nullable=False, default='Pending')  # Pending, Done, Skipped
    updated_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'remediation_id': self.remediation_id,
            'finding_id': self.finding_id,
            'action': self.action,
            'status': self.status,
            'updated_at': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
            'finding': self.finding.to_dict() if self.finding else None
        }


def init_models():
    # Placeholder for any model init hooks
    pass

