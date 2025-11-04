from datetime import datetime
from . import db

class Evidence(db.Model):
    __tablename__ = 'evidence'
    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    relative_path = db.Column(db.String(512), nullable=False)  # relative to STORAGE_DIR
    content_type = db.Column(db.String(128))
    size_bytes = db.Column(db.Integer, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    tags = db.Column(db.JSON, default=list)
    audit_id = db.Column(db.String(128))
    meta_json = db.Column(db.JSON, default=dict)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'original_filename': self.original_filename,
            'stored_filename': self.stored_filename,
            'relative_path': self.relative_path,
            'content_type': self.content_type,
            'size_bytes': self.size_bytes,
            'sha256': self.sha256,
            'tags': self.tags or [],
            'audit_id': self.audit_id,
            'meta': self.meta_json or {},
            'uploaded_at': self.uploaded_at.isoformat() + 'Z',
        }

class Bundle(db.Model):
    __tablename__ = 'bundle'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    audit_id = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    bundle_hash = db.Column(db.String(64))
    item_count = db.Column(db.Integer, default=0)

    items = db.relationship('BundleItem', back_populates='bundle', cascade='all, delete-orphan')

    def to_dict(self, include_items=False):
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'audit_id': self.audit_id,
            'created_at': self.created_at.isoformat() + 'Z',
            'bundle_hash': self.bundle_hash,
            'item_count': self.item_count,
        }
        if include_items:
            data['evidence'] = [bi.evidence.to_dict() for bi in self.items]
        return data

class BundleItem(db.Model):
    __tablename__ = 'bundle_item'
    id = db.Column(db.Integer, primary_key=True)
    bundle_id = db.Column(db.Integer, db.ForeignKey('bundle.id'), nullable=False)
    evidence_id = db.Column(db.Integer, db.ForeignKey('evidence.id'), nullable=False)

    bundle = db.relationship('Bundle', back_populates='items')
    evidence = db.relationship('Evidence')

