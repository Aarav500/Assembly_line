import datetime
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='viewer')  # admin, reviewer, viewer

    policies = db.relationship('Policy', backref='owner', lazy=True)


class Policy(db.Model):
    __tablename__ = 'policies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Draft')  # Draft, In Review, Approved, Rejected
    category = db.Column(db.String(100), nullable=False, default='General')
    version = db.Column(db.Integer, nullable=False, default=1)

    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    approvals = db.relationship('Approval', backref='policy', lazy=True)


class Approval(db.Model):
    __tablename__ = 'approvals'
    id = db.Column(db.Integer, primary_key=True)

    policy_id = db.Column(db.Integer, db.ForeignKey('policies.id'), nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    status = db.Column(db.String(20), nullable=False, default='Pending')  # Pending, Approved, Rejected
    comment = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    decided_at = db.Column(db.DateTime)

    approver = db.relationship('User', backref=db.backref('approvals', lazy=True))

