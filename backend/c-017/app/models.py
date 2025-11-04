from datetime import datetime, timezone
from typing import List
from .extensions import db

# Association tables
user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class User(db.Model, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255))
    password_hash = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    roles = db.relationship("Role", secondary=user_roles, back_populates="users")
    oauth_accounts = db.relationship("OAuthAccount", back_populates="user", cascade="all, delete-orphan")

    def has_role(self, role_name: str) -> bool:
        return any(r.name == role_name for r in self.roles)

    @property
    def permissions(self) -> List[str]:
        p: set[str] = set()
        for r in self.roles:
            p.update([perm.name for perm in r.permissions])
        return sorted(p)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "roles": [r.name for r in self.roles],
            "permissions": self.permissions,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Role(db.Model, TimestampMixin):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255))

    users = db.relationship("User", secondary=user_roles, back_populates="roles")
    permissions = db.relationship("Permission", secondary=role_permissions, back_populates="roles")


class Permission(db.Model, TimestampMixin):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255))

    roles = db.relationship("Role", secondary=role_permissions, back_populates="permissions")


class OAuthAccount(db.Model, TimestampMixin):
    __tablename__ = "oauth_accounts"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False, index=True)
    provider_user_id = db.Column(db.String(255), nullable=False, index=True)
    email = db.Column(db.String(255))
    token = db.Column(db.Text)  # JSON string

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user = db.relationship("User", back_populates="oauth_accounts")

    __table_args__ = (db.UniqueConstraint("provider", "provider_user_id", name="uq_provider_user"),)


class TokenBlocklist(db.Model, TimestampMixin):
    __tablename__ = "token_blocklist"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), unique=True, index=True, nullable=False)
    token_type = db.Column(db.String(16), nullable=False)  # access or refresh
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), index=True)
    revoked = db.Column(db.Boolean, default=True, nullable=False)

