import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index


db = SQLAlchemy()


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    source_type = db.Column(db.String(20), nullable=False)  # file | url | repo
    source = db.Column(db.String(1024))  # path or url or repo file path
    title = db.Column(db.String(512))
    content = db.Column(db.Text)
    meta = db.Column(db.Text)  # JSON string

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_documents_source_type', 'source_type'),
        Index('idx_documents_created_at', 'created_at'),
    )

    def to_dict(self, include_content=True):
        try:
            meta_obj = json.loads(self.meta) if self.meta else {}
        except Exception:
            meta_obj = {}
        data = {
            'id': self.id,
            'source_type': self.source_type,
            'source': self.source,
            'title': self.title,
            'created_at': self.created_at.isoformat() + 'Z',
            'updated_at': self.updated_at.isoformat() + 'Z',
            'meta': meta_obj,
        }
        if include_content:
            data['content'] = self.content
        return data

