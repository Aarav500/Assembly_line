from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index
from datetime import datetime


db = SQLAlchemy()


class BacklogItem(db.Model):
    __tablename__ = 'backlog_items'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    file_path = db.Column(db.Text, nullable=False, index=True)
    line_number = db.Column(db.Integer, nullable=True)
    text = db.Column(db.Text, nullable=False)
    tag = db.Column(db.String(16), nullable=False, default='TODO', index=True)
    status = db.Column(db.String(16), nullable=False, default='open', index=True)  # open, resolved

    first_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'text': self.text,
            'tag': self.tag,
            'status': self.status,
            'first_seen_at': self.first_seen_at.isoformat() + 'Z' if self.first_seen_at else None,
            'last_seen_at': self.last_seen_at.isoformat() + 'Z' if self.last_seen_at else None,
            'updated_at': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
        }


Index('idx_backlog_items_status_tag', BacklogItem.status, BacklogItem.tag)

