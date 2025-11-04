from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Table
from sqlalchemy.orm import relationship


db = SQLAlchemy()

bundle_artifacts = Table(
    'bundle_artifacts', db.Model.metadata,
    Column('bundle_id', Integer, ForeignKey('bundles.id', ondelete='CASCADE'), primary_key=True),
    Column('artifact_id', Integer, ForeignKey('artifacts.id', ondelete='CASCADE'), primary_key=True),
)


class Artifact(db.Model):
    __tablename__ = 'artifacts'
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    path = Column(Text, nullable=False)
    size = Column(Integer, nullable=False)
    checksum = Column(String(128), nullable=False)
    metadata = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'path': self.path,
            'size': self.size,
            'checksum': self.checksum,
            'metadata': self.metadata,
            'uploaded_at': self.uploaded_at.isoformat() + 'Z'
        }


class Bundle(db.Model):
    __tablename__ = 'bundles'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    zip_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    artifacts = relationship('Artifact', secondary=bundle_artifacts, backref='bundles', lazy='joined')

    def to_dict(self, include_artifacts=False):
        data = {
            'id': self.id,
            'name': self.name,
            'zip_path': self.zip_path,
            'created_at': self.created_at.isoformat() + 'Z'
        }
        if include_artifacts:
            data['artifacts'] = [a.to_dict() for a in self.artifacts]
        return data


class ApprovalRequest(db.Model):
    __tablename__ = 'approval_requests'
    id = Column(Integer, primary_key=True)
    bundle_id = Column(Integer, ForeignKey('bundles.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), default='PENDING', nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    due_at = Column(DateTime, nullable=True)

    bundle = relationship('Bundle', lazy='joined')
    approvers = relationship('Approver', backref='request', cascade='all, delete-orphan', lazy='joined')

    def to_dict(self, include_approvers=False):
        data = {
            'id': self.id,
            'bundle_id': self.bundle_id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat() + 'Z',
            'due_at': self.due_at.isoformat() + 'Z' if self.due_at else None,
            'bundle': self.bundle.to_dict() if self.bundle else None,
        }
        if include_approvers:
            data['approvers'] = [a.to_dict() for a in self.approvers]
        return data


class Approver(db.Model):
    __tablename__ = 'approvers'
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey('approval_requests.id', ondelete='CASCADE'), nullable=False)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    token_hash = Column(String(128), nullable=False)
    decision = Column(String(32), default='PENDING', nullable=False)
    signature_text = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)
    signer_ip = Column(String(64), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'request_id': self.request_id,
            'email': self.email,
            'name': self.name,
            'decision': self.decision,
            'signature_text': self.signature_text,
            'comment': self.comment,
            'signer_ip': self.signer_ip,
            'approved_at': self.approved_at.isoformat() + 'Z' if self.approved_at else None,
        }

