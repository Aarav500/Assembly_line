from datetime import datetime
from typing import Optional
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import validates


db = SQLAlchemy()


class Policy(db.Model):
    __tablename__ = "policies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Days after creation or override until auto-archive
    auto_archive_after_days = db.Column(db.Integer, nullable=True)

    # Days after archive until auto-purge
    auto_purge_after_days = db.Column(db.Integer, nullable=True)

    # If true, perform hard delete on purge
    purge_hard = db.Column(db.Boolean, default=False, nullable=False)

    active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "auto_archive_after_days": self.auto_archive_after_days,
            "auto_purge_after_days": self.auto_purge_after_days,
            "purge_hard": self.purge_hard,
            "active": self.active,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


class Idea(db.Model):
    __tablename__ = "ideas"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.String(16), default="active", nullable=False
    )  # active | archived | purged

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    archived_at = db.Column(db.DateTime, nullable=True)
    purged_at = db.Column(db.DateTime, nullable=True)

    # Optional explicit expiration (archive) timestamp
    expires_at = db.Column(db.DateTime, nullable=True)

    # Policy association
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=True)
    policy = db.relationship("Policy")

    # Optional per-idea override for purge hardness
    purge_hard_override = db.Column(db.Boolean, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "status": self.status,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
            "archived_at": self.archived_at.isoformat() + "Z" if self.archived_at else None,
            "purged_at": self.purged_at.isoformat() + "Z" if self.purged_at else None,
            "expires_at": self.expires_at.isoformat() + "Z" if self.expires_at else None,
            "policy": self.policy.to_dict() if self.policy else None,
            "purge_hard_override": self.purge_hard_override,
        }

    @validates("status")
    def validate_status(self, key, value):
        if value not in ("active", "archived", "purged"):
            raise ValueError("Invalid status")
        return value

