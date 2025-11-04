from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

role_permissions = db.Table(
    'role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    memberships = db.relationship('ProjectMember', back_populates='user', cascade='all, delete-orphan')
    requests = db.relationship('ApprovalRequest', back_populates='requester', foreign_keys='ApprovalRequest.requester_id')

    def __repr__(self):
        return f"<User {self.username}>"


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship('ProjectMember', back_populates='project', cascade='all, delete-orphan')
    approvals = db.relationship('ApprovalRequest', back_populates='project', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Project {self.name}>"


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text)

    permissions = db.relationship('Permission', secondary=role_permissions, backref='roles')

    def __repr__(self):
        return f"<Role {self.name}>"


class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text)

    def __repr__(self):
        return f"<Permission {self.name}>"


class ProjectMember(db.Model):
    __tablename__ = 'project_members'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship('Project', back_populates='members')
    user = db.relationship('User', back_populates='memberships')
    role = db.relationship('Role')

    __table_args__ = (db.UniqueConstraint('project_id', 'user_id', name='uq_project_user'),)


class ApprovalRequest(db.Model):
    __tablename__ = 'approval_requests'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    requested_role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)
    requested_permission = db.Column(db.String(80), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='PENDING')  # PENDING, APPROVED, DENIED, CANCELED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    decided_at = db.Column(db.DateTime, nullable=True)
    decided_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    decision_notes = db.Column(db.Text, nullable=True)

    project = db.relationship('Project', back_populates='approvals')
    requester = db.relationship('User', foreign_keys=[requester_id], back_populates='requests')
    target_user = db.relationship('User', foreign_keys=[target_user_id])
    decided_by = db.relationship('User', foreign_keys=[decided_by_id])
    requested_role = db.relationship('Role')

    def __repr__(self):
        return f"<ApprovalRequest {self.id} {self.status}>"


def ensure_seed_data():
    # Create permissions
    perm_names = [
        ("view_project", "Can view project details"),
        ("edit_project", "Can edit project details"),
        ("manage_members", "Can add/remove members and assign roles"),
        ("approve_requests", "Can approve or deny approval requests")
    ]
    for name, desc in perm_names:
        if not Permission.query.filter_by(name=name).first():
            db.session.add(Permission(name=name, description=desc))
    db.session.commit()

    # Create roles
    role_specs = {
        "Owner": ["view_project", "edit_project", "manage_members", "approve_requests"],
        "Maintainer": ["view_project", "edit_project", "approve_requests", "manage_members"],
        "Viewer": ["view_project"]
    }
    for role_name, perms in role_specs.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name, description=f"{role_name} role")
            db.session.add(role)
            db.session.flush()
        role.permissions = [Permission.query.filter_by(name=p).first() for p in perms]
    db.session.commit()

