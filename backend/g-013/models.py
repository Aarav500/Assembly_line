from datetime import datetime
from sqlalchemy.dialects.sqlite import JSON
from db import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Dataset(db.Model, TimestampMixin):
    __tablename__ = 'datasets'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    version = db.Column(db.String(128), nullable=True)
    uri = db.Column(db.String(1024), nullable=True)
    local_path = db.Column(db.String(1024), nullable=True)
    checksum = db.Column(db.String(128), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)
    metadata = db.Column(JSON, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'version': self.version,
            'uri': self.uri,
            'local_path': self.local_path,
            'checksum': self.checksum,
            'size_bytes': self.size_bytes,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class CodeVersion(db.Model, TimestampMixin):
    __tablename__ = 'code_versions'
    id = db.Column(db.Integer, primary_key=True)
    repo_url = db.Column(db.String(1024), nullable=True)
    commit_hash = db.Column(db.String(128), nullable=False)
    branch = db.Column(db.String(255), nullable=True)
    patch_path = db.Column(db.String(1024), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'repo_url': self.repo_url,
            'commit_hash': self.commit_hash,
            'branch': self.branch,
            'patch_path': self.patch_path,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class Environment(db.Model, TimestampMixin):
    __tablename__ = 'environments'
    id = db.Column(db.Integer, primary_key=True)
    python_version = db.Column(db.String(64), nullable=True)
    pip_freeze = db.Column(db.Text, nullable=True)
    docker_image = db.Column(db.String(512), nullable=True)
    conda_env = db.Column(db.Text, nullable=True)
    os_info = db.Column(JSON, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'python_version': self.python_version,
            'pip_freeze': self.pip_freeze,
            'docker_image': self.docker_image,
            'conda_env': self.conda_env,
            'os_info': self.os_info,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class Run(db.Model, TimestampMixin):
    __tablename__ = 'runs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(64), default='created')
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    random_seed = db.Column(db.Integer, nullable=True)
    parameters = db.Column(JSON, nullable=True)
    metrics = db.Column(JSON, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    code_version_id = db.Column(db.Integer, db.ForeignKey('code_versions.id'), nullable=True)
    environment_id = db.Column(db.Integer, db.ForeignKey('environments.id'), nullable=True)

    code_version = db.relationship('CodeVersion')
    environment = db.relationship('Environment')
    datasets = db.relationship('RunDataset', back_populates='run', cascade='all, delete-orphan')
    artifacts = db.relationship('Artifact', back_populates='run', cascade='all, delete-orphan')
    bundles = db.relationship('Bundle', back_populates='run', cascade='all, delete-orphan')

    def to_dict(self, include_children=True):
        base = {
            'id': self.id,
            'name': self.name,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'random_seed': self.random_seed,
            'parameters': self.parameters,
            'metrics': self.metrics,
            'notes': self.notes,
            'code_version_id': self.code_version_id,
            'environment_id': self.environment_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
        if include_children:
            base['datasets'] = [rd.to_dict() for rd in self.datasets]
            base['artifacts'] = [a.to_dict() for a in self.artifacts]
            base['bundles'] = [b.to_dict() for b in self.bundles]
            base['code_version'] = self.code_version.to_dict() if self.code_version else None
            base['environment'] = self.environment.to_dict() if self.environment else None
        return base


class RunDataset(db.Model, TimestampMixin):
    __tablename__ = 'run_datasets'
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('runs.id'), nullable=False)
    dataset_id = db.Column(db.Integer, db.ForeignKey('datasets.id'), nullable=False)
    role = db.Column(db.String(64), nullable=False)  # e.g., train/val/test/holdout
    snapshot_path = db.Column(db.String(1024), nullable=True)

    run = db.relationship('Run', back_populates='datasets')
    dataset = db.relationship('Dataset')

    def to_dict(self):
        return {
            'id': self.id,
            'run_id': self.run_id,
            'dataset_id': self.dataset_id,
            'role': self.role,
            'snapshot_path': self.snapshot_path,
            'dataset': self.dataset.to_dict() if self.dataset else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class Artifact(db.Model, TimestampMixin):
    __tablename__ = 'artifacts'
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('runs.id'), nullable=False)
    type = db.Column(db.String(128), nullable=False)  # model, log, metrics, plot, dataset_snapshot, manifest
    path = db.Column(db.String(1024), nullable=False)
    checksum = db.Column(db.String(128), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)
    mime_type = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)

    run = db.relationship('Run', back_populates='artifacts')

    def to_dict(self):
        return {
            'id': self.id,
            'run_id': self.run_id,
            'type': self.type,
            'path': self.path,
            'checksum': self.checksum,
            'size_bytes': self.size_bytes,
            'mime_type': self.mime_type,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class Bundle(db.Model, TimestampMixin):
    __tablename__ = 'bundles'
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('runs.id'), nullable=False)
    path = db.Column(db.String(1024), nullable=False)
    checksum = db.Column(db.String(128), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)

    run = db.relationship('Run', back_populates='bundles')

    def to_dict(self):
        return {
            'id': self.id,
            'run_id': self.run_id,
            'path': self.path,
            'checksum': self.checksum,
            'size_bytes': self.size_bytes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

