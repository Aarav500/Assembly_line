from datetime import datetime
from enum import Enum
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class RoleEnum(str, Enum):
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"

class ClassificationEnum(str, Enum):
    public = "public"
    confidential = "confidential"
    restricted = "restricted"

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(RoleEnum), nullable=False, default=RoleEnum.viewer)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    datasets_owned = db.relationship("Dataset", backref="owner", lazy=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_safe_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role.value,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() + "Z",
        }

class Dataset(db.Model):
    __tablename__ = "datasets"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    classification = db.Column(db.Enum(ClassificationEnum), nullable=False, default=ClassificationEnum.public)
    data = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    accesses = db.relationship("DatasetAccess", backref="dataset", lazy=True, cascade="all, delete-orphan")

    def to_meta_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "classification": self.classification.value,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat() + "Z",
        }

class DatasetAccess(db.Model):
    __tablename__ = "dataset_accesses"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("datasets.id"), nullable=False, index=True)
    can_read = db.Column(db.Boolean, default=True, nullable=False)
    granted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    granted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
    granter = db.relationship("User", foreign_keys=[granted_by])

class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(128), nullable=False)
    resource_type = db.Column(db.String(64), nullable=True)
    resource_id = db.Column(db.String(128), nullable=True)
    success = db.Column(db.Boolean, default=True, nullable=False)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    method = db.Column(db.String(16), nullable=True)
    path = db.Column(db.String(512), nullable=True)
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "success": self.success,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "method": self.method,
            "path": self.path,
            "message": self.message,
            "created_at": self.created_at.isoformat() + "Z",
        }

