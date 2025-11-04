from datetime import datetime
from flask_login import UserMixin
from .extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


users_roles = db.Table(
    'users_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id', ondelete="CASCADE"), primary_key=True),
)


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(255))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    profile = db.relationship('Profile', backref='user', uselist=False, cascade="all, delete-orphan")
    roles = db.relationship('Role', secondary=users_roles, backref=db.backref('users', lazy='dynamic'))

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def has_role(self, role_name: str) -> bool:
        return any(r.name == role_name for r in self.roles)

    def get_id(self):
        return str(self.id)

    def to_dict(self, include_email=True, include_roles=True, include_profile=True):
        data = {
            "id": self.id,
            "email": self.email if include_email else None,
            "is_active": self.is_active,
            "is_email_verified": self.is_email_verified,
            "created_at": self.created_at.isoformat() + 'Z' if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + 'Z' if self.updated_at else None,
        }
        if include_roles:
            data["roles"] = [r.to_dict() for r in self.roles]
        if include_profile and self.profile:
            data["profile"] = self.profile.to_dict()
        return data


class Profile(db.Model):
    __tablename__ = 'profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), unique=True, nullable=False)
    full_name = db.Column(db.String(120))
    bio = db.Column(db.Text)
    avatar_url = db.Column(db.String(512))
    phone = db.Column(db.String(32))
    timezone = db.Column(db.String(64))

    def to_dict(self):
        return {
            "full_name": self.full_name,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "phone": self.phone,
            "timezone": self.timezone,
        }


class EmailVerificationToken(db.Model):
    __tablename__ = 'email_verification_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    token_hash = db.Column(db.String(255), nullable=False)
    email_to_verify = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('email_tokens', lazy='dynamic'))


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    token_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('reset_tokens', lazy='dynamic'))

