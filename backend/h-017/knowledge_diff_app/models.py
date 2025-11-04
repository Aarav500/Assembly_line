from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func


db = SQLAlchemy()


class Source(db.Model):
    __tablename__ = 'sources'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(2048), nullable=False)
    selector = db.Column(db.String(255), nullable=True)  # optional CSS selector
    interval_minutes = db.Column(db.Integer, default=60, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    notify_email = db.Column(db.String(1024), nullable=True)  # comma-separated emails
    notify_webhook = db.Column(db.String(2048), nullable=True)

    last_checked = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    versions = db.relationship('Version', backref='source', lazy=True, order_by='desc(Version.created_at)')

    def next_due(self) -> datetime:
        if not self.last_checked:
            return datetime.utcnow() - timedelta(seconds=1)
        return self.last_checked + timedelta(minutes=self.interval_minutes)

    def is_due(self) -> bool:
        return self.active and self.next_due() <= datetime.utcnow()


class Version(db.Model):
    __tablename__ = 'versions'
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('sources.id'), nullable=False)
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    content_text = db.Column(db.Text, nullable=False)

    # diff relative to previous version (if any)
    diff_to_prev = db.Column(db.Text, nullable=True)
    html_diff_to_prev = db.Column(db.Text, nullable=True)
    added_lines = db.Column(db.Integer, default=0, nullable=False)
    removed_lines = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @staticmethod
    def last_for_source(source_id):
        return Version.query.filter_by(source_id=source_id).order_by(Version.created_at.desc()).first()

    @staticmethod
    def count_for_source(source_id):
        return db.session.query(func.count(Version.id)).filter(Version.source_id == source_id).scalar() or 0

