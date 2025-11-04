from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, String, LargeBinary, Boolean, DateTime


db = SQLAlchemy()


class Key(db.Model):
    __tablename__ = 'keys'
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    tenant_id = Column(String(255), nullable=False, index=True)
    wrapped_key = Column(LargeBinary, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(String(255), nullable=True)


class AuditEvent(db.Model):
    __tablename__ = 'audit_events'
    id = Column(String(36), primary_key=True)
    ts = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    actor_id = Column(String(255), nullable=True)
    actor_role = Column(String(64), nullable=True)
    tenant_id = Column(String(255), nullable=True, index=True)
    action = Column(String(255), nullable=False, index=True)
    object_type = Column(String(64), nullable=True)
    object_id = Column(String(255), nullable=True)
    success = Column(Boolean, default=True, nullable=False, index=True)
    ip = Column(String(64), nullable=True)
    message = Column(String(512), nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not getattr(self, 'id', None):
            import uuid
            self.id = str(uuid.uuid4())


def init_db():
    db.create_all()

