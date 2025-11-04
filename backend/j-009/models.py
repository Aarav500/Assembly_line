from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


db = SQLAlchemy()


class BlueprintItem(db.Model):
    __tablename__ = 'blueprint_items'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    author = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    view_count = db.Column(db.Integer, nullable=False, default=0)
    download_count = db.Column(db.Integer, nullable=False, default=0)
    file_name = db.Column(db.String(255), nullable=False)

    ratings = db.relationship('Rating', backref='blueprint', lazy='dynamic', cascade='all, delete-orphan')

    def average_rating(self):
        avg = self.ratings.with_entities(db.func.avg(Rating.score)).scalar()
        return round(float(avg), 2) if avg is not None else 0.0

    def rating_count(self):
        return self.ratings.count()


class Rating(db.Model):
    __tablename__ = 'ratings'

    id = db.Column(db.Integer, primary_key=True)
    blueprint_id = db.Column(db.Integer, db.ForeignKey('blueprint_items.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('blueprint_id', 'ip_address', name='uq_rating_per_ip'),
    )

    def __repr__(self):
        return f"<Rating blueprint_id={self.blueprint_id} score={self.score}>"

