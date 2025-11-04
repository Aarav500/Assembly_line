from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import String, Text, DateTime, Boolean
from .extensions import db
import json


class Environment(db.Model):
    __tablename__ = "environments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "description": self.description}


class IdentityProvider(db.Model):
    __tablename__ = "identity_providers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    audience: Mapped[str] = mapped_column(String(256), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(16), nullable=False, default="RS256")
    jwks_uri: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    jwks_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "issuer": self.issuer,
            "audience": self.audience,
            "algorithm": self.algorithm,
            "jwks_uri": self.jwks_uri,
            "enabled": self.enabled,
            "has_inline_jwks": bool(self.jwks_json),
        }


class Role(db.Model):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "description": self.description}


class RoleBinding(db.Model):
    __tablename__ = "role_bindings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    role_id: Mapped[str] = mapped_column(String(36), db.ForeignKey("roles.id"), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(36), db.ForeignKey("identity_providers.id"), nullable=False)
    required_claim: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    required_value: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    allowed_environments_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    __table_args__ = (
        UniqueConstraint("role_id", "provider_id", name="uq_role_provider"),
    )

    def allowed_environments(self) -> List[str]:
        try:
            return json.loads(self.allowed_environments_json or "[]")
        except Exception:
            return []

    def set_allowed_environments(self, envs: List[str]):
        self.allowed_environments_json = json.dumps(envs or [])

    def to_dict(self) -> Dict[str, Any]:
        role = db.session.get(Role, self.role_id)
        prov = db.session.get(IdentityProvider, self.provider_id)
        return {
            "id": self.id,
            "role": role.name if role else None,
            "provider": prov.name if prov else None,
            "provider_id": self.provider_id,
            "required_claim": self.required_claim,
            "required_value": self.required_value,
            "allowed_environments": self.allowed_environments(),
        }


class SessionCredential(db.Model):
    __tablename__ = "session_credentials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_sub: Mapped[str] = mapped_column(String(256), nullable=False)
    role_name: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_name: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(36), db.ForeignKey("identity_providers.id"), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "jti": self.jti,
            "user_sub": self.user_sub,
            "role_name": self.role_name,
            "environment_name": self.environment_name,
            "provider_id": self.provider_id,
            "issued_at": self.issued_at.isoformat() + "Z",
            "expires_at": self.expires_at.isoformat() + "Z",
            "status": self.status,
        }

