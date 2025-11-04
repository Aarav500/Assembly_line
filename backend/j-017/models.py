from datetime import datetime
from database import db

class Profile(db.Model):
    __tablename__ = 'profiles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255), default='')
    temperature = db.Column(db.Float, default=0.7)
    top_p = db.Column(db.Float, default=1.0)
    presence_penalty = db.Column(db.Float, default=0.0)
    frequency_penalty = db.Column(db.Float, default=0.0)
    max_tokens = db.Column(db.Integer, default=300)
    top_k = db.Column(db.Integer, nullable=True)
    seed = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "presence_penalty": self.presence_penalty,
            "frequency_penalty": self.frequency_penalty,
            "max_tokens": self.max_tokens,
            "top_k": self.top_k,
            "seed": self.seed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    active_profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=True)
    active_profile = db.relationship('Profile', foreign_keys=[active_profile_id])
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, include_profile=True):
        data = {
            "id": self.id,
            "username": self.username,
            "active_profile_id": self.active_profile_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_profile and self.active_profile:
            data["active_profile"] = self.active_profile.to_dict()
        else:
            data["active_profile"] = None
        return data

