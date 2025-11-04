from datetime import datetime
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Dataset(db.Model):
    __tablename__ = "datasets"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(512), nullable=False)
    original_name = db.Column(db.String(512), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=True)

    schema_json = db.Column(db.Text, nullable=True)
    quality_metrics_json = db.Column(db.Text, nullable=True)
    sample_rows_json = db.Column(db.Text, nullable=True)

    row_count = db.Column(db.Integer, nullable=True)
    col_count = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Dataset id={self.id} name={self.name}>"

