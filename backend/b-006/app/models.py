from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint
from sqlalchemy.types import JSON


db = SQLAlchemy()


class Taxonomy(db.Model):
    __tablename__ = 'taxonomies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    default_threshold = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    terms = relationship('Term', back_populates='taxonomy', cascade='all, delete-orphan')

    def to_dict(self, include_terms=False):
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'default_threshold': self.default_threshold,
            'created_at': self.created_at.isoformat(),
        }
        if include_terms:
            data['terms'] = [t.to_dict() for t in self.terms]
        return data


class Term(db.Model):
    __tablename__ = 'terms'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    taxonomy_id = db.Column(db.Integer, db.ForeignKey('taxonomies.id'), nullable=False)
    keywords = db.Column(JSON, nullable=False, default=list)  # list of patterns or dicts {pattern, weight}
    threshold = db.Column(db.Float, nullable=True)
    weight = db.Column(db.Float, nullable=True)  # overall weight multiplier for the term
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    taxonomy = relationship('Taxonomy', back_populates='terms')

    __table_args__ = (
        UniqueConstraint('taxonomy_id', 'name', name='uq_term_taxonomy_name'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'taxonomy_id': self.taxonomy_id,
            'keywords': self.keywords,
            'threshold': self.threshold,
            'weight': self.weight,
            'created_at': self.created_at.isoformat(),
        }


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    term_links = relationship('DocumentTerm', back_populates='document', cascade='all, delete-orphan')

    def to_dict(self, include_tags=False):
        data = {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
        }
        if include_tags:
            data['tags'] = [link.to_dict() for link in self.term_links]
        return data


class DocumentTerm(db.Model):
    __tablename__ = 'document_terms'

    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), primary_key=True)
    term_id = db.Column(db.Integer, db.ForeignKey('terms.id'), primary_key=True)
    score = db.Column(db.Float, nullable=False)
    matched_keywords = db.Column(JSON, nullable=False, default=list)  # which patterns matched

    document = relationship('Document', back_populates='term_links')
    term = relationship('Term')

    def to_dict(self):
        return {
            'document_id': self.document_id,
            'term_id': self.term_id,
            'term_name': self.term.name if self.term else None,
            'taxonomy_id': self.term.taxonomy_id if self.term else None,
            'score': round(self.score, 4),
            'matched_keywords': self.matched_keywords,
        }

