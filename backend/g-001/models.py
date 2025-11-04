from datetime import datetime
from sqlalchemy import UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from db import db

class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

model_tags = db.Table(
    'model_tags',
    db.Column('model_id', db.Integer, db.ForeignKey('models.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)
)

class Model(db.Model, TimestampMixin):
    __tablename__ = 'models'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    archived = db.Column(db.Boolean, default=False, nullable=False)

    versions = db.relationship('ModelVersion', backref='model', cascade='all, delete-orphan', lazy=True)
    tags = db.relationship('Tag', secondary=model_tags, backref=db.backref('models', lazy='dynamic'))

    def to_dict(self, with_versions=False):
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'archived': self.archived,
            'tags': [t.name for t in self.tags],
            'created_at': self.created_at.isoformat()+'Z',
            'updated_at': self.updated_at.isoformat()+'Z',
        }
        if with_versions:
            data['versions'] = [v.to_dict(include_metadata=True) for v in self.versions]
        return data

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)

class ModelVersion(db.Model, TimestampMixin):
    __tablename__ = 'model_versions'
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.Integer, db.ForeignKey('models.id', ondelete='CASCADE'), nullable=False)
    version = db.Column(db.String(128), nullable=True)  # optional human version label
    stage = db.Column(db.String(64), nullable=True)  # e.g., None, Staging, Production, Archived
    code_commit = db.Column(db.String(128), nullable=True)
    created_by = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint('model_id', 'version', name='uq_model_version_label'),
    )

    artifacts = db.relationship('Artifact', backref='model_version', cascade='all, delete-orphan', lazy=True)
    metadata_revisions = db.relationship('MetadataRevision', backref='model_version', cascade='all, delete-orphan', lazy=True, order_by='MetadataRevision.revision_num')

    def current_metadata(self):
        if not self.metadata_revisions:
            return None
        return self.metadata_revisions[-1].data

    def to_dict(self, include_metadata=False, include_lineage=False):
        data = {
            'id': self.id,
            'model_id': self.model_id,
            'version': self.version,
            'stage': self.stage,
            'code_commit': self.code_commit,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat()+'Z',
            'updated_at': self.updated_at.isoformat()+'Z',
            'artifacts': [a.to_dict() for a in self.artifacts],
        }
        if include_metadata:
            data['metadata'] = self.current_metadata()
            data['metadata_revisions'] = [mr.to_dict(include_data=False) for mr in self.metadata_revisions]
        if include_lineage:
            data['lineage'] = {
                'parents': [e.to_dict() for e in LineageEdge.query.filter_by(child_type='model_version', child_id=self.id).all()],
                'children': [e.to_dict() for e in LineageEdge.query.filter_by(parent_type='model_version', parent_id=self.id).all()],
            }
        return data

class MetadataRevision(db.Model):
    __tablename__ = 'metadata_revisions'
    id = db.Column(db.Integer, primary_key=True)
    model_version_id = db.Column(db.Integer, db.ForeignKey('model_versions.id', ondelete='CASCADE'), nullable=False)
    revision_num = db.Column(db.Integer, nullable=False)
    data = db.Column(SQLITE_JSON, nullable=False)
    message = db.Column(db.String(512), nullable=True)
    author = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('model_version_id', 'revision_num', name='uq_version_revision'),
    )

    def to_dict(self, include_data=True):
        d = {
            'id': self.id,
            'model_version_id': self.model_version_id,
            'revision_num': self.revision_num,
            'message': self.message,
            'author': self.author,
            'created_at': self.created_at.isoformat()+'Z',
        }
        if include_data:
            d['data'] = self.data
        return d

class Artifact(db.Model, TimestampMixin):
    __tablename__ = 'artifacts'
    id = db.Column(db.Integer, primary_key=True)
    model_version_id = db.Column(db.Integer, db.ForeignKey('model_versions.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(64), nullable=False)  # e.g., weights, metrics, signature, docker-image
    uri = db.Column(db.String(1024), nullable=False)
    sha256 = db.Column(db.String(64), nullable=True)
    size = db.Column(db.Integer, nullable=True)
    extra = db.Column(SQLITE_JSON, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'model_version_id': self.model_version_id,
            'type': self.type,
            'uri': self.uri,
            'sha256': self.sha256,
            'size': self.size,
            'extra': self.extra,
            'created_at': self.created_at.isoformat()+'Z',
            'updated_at': self.updated_at.isoformat()+'Z',
        }

class Dataset(db.Model, TimestampMixin):
    __tablename__ = 'datasets'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    uri = db.Column(db.String(1024), nullable=True)
    description = db.Column(db.Text, nullable=True)
    sha256 = db.Column(db.String(64), nullable=True)
    metadata = db.Column('metadata_json', SQLITE_JSON, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'uri': self.uri,
            'description': self.description,
            'sha256': self.sha256,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()+'Z',
            'updated_at': self.updated_at.isoformat()+'Z',
        }

class LineageEdge(db.Model):
    __tablename__ = 'lineage_edges'
    id = db.Column(db.Integer, primary_key=True)
    parent_type = db.Column(db.String(32), nullable=False)  # model_version or dataset
    parent_id = db.Column(db.Integer, nullable=False)
    child_type = db.Column(db.String(32), nullable=False)  # model_version or dataset
    child_id = db.Column(db.Integer, nullable=False)
    relation = db.Column(db.String(64), nullable=False)  # derives_from, trained_on, evaluated_on
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("parent_type in ('model_version','dataset')"),
        CheckConstraint("child_type in ('model_version','dataset')"),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'parent': {'type': self.parent_type, 'id': self.parent_id},
            'child': {'type': self.child_type, 'id': self.child_id},
            'relation': self.relation,
            'created_at': self.created_at.isoformat()+'Z',
        }

