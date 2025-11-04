from datetime import datetime
import uuid
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_seller = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    templates = db.relationship('Template', backref='owner', lazy=True)
    purchases = db.relationship('Purchase', backref='buyer', lazy=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"


class Template(db.Model):
    __tablename__ = 'templates'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price_cents = db.Column(db.Integer, nullable=False, default=0)
    currency = db.Column(db.String(10), nullable=False, default='usd')
    is_published = db.Column(db.Boolean, default=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    versions = db.relationship('TemplateVersion', backref='template', lazy=True, order_by='desc(TemplateVersion.created_at)')
    purchases = db.relationship('Purchase', backref='template', lazy=True)

    def latest_version(self):
        return self.versions[0] if self.versions else None

    def __repr__(self):
        return f"<Template {self.title} ${self.price_cents/100:.2f}>"


class TemplateVersion(db.Model):
    __tablename__ = 'template_versions'
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('templates.id'), nullable=False)
    version = db.Column(db.String(50), nullable=False)  # semantic version string
    changelog = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(500), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TemplateVersion {self.template_id} v{self.version}>"


class Purchase(db.Model):
    __tablename__ = 'purchases'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('templates.id'), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(10), nullable=False, default='usd')
    payment_provider = db.Column(db.String(50), nullable=True)
    payment_id = db.Column(db.String(255), nullable=True)  # e.g., Stripe session/payment intent id
    status = db.Column(db.String(50), nullable=False, default='pending')  # pending, paid, failed, canceled
    license_key = db.Column(db.String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'template_id', name='uq_user_template_once'),
    )

    def is_paid(self) -> bool:
        return self.status == 'paid'

    def __repr__(self):
        return f"<Purchase user={self.user_id} template={self.template_id} status={self.status}>"


