import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import Index, UniqueConstraint
from .extensions import db


def default_uuid():
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(UUID(as_uuid=False), primary_key=True, default=default_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False)
    full_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email}>"


class AuditEvent(db.Model):
    __tablename__ = "audit_events"

    id = db.Column(UUID(as_uuid=False), primary_key=True, default=default_uuid)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Actor / Request context
    user_id = db.Column(db.String(64), nullable=True, index=True)
    request_id = db.Column(db.String(64), nullable=True, index=True)
    ip = db.Column(db.String(64), nullable=True)

    # Event details
    event_type = db.Column(db.String(32), nullable=False, index=True)  # api_call | user_action | data_change
    action = db.Column(db.String(128), nullable=True, index=True)
    method = db.Column(db.String(16), nullable=True)
    path = db.Column(db.String(1024), nullable=True, index=True)
    status_code = db.Column(db.Integer, nullable=True)

    user_agent = db.Column(db.String(512), nullable=True)
    headers = db.Column(JSONB, nullable=True)
    query_params = db.Column(JSONB, nullable=True)
    request_body = db.Column(db.Text, nullable=True)
    details = db.Column(JSONB, nullable=True)

    # Tamper-evidence chain
    previous_hash = db.Column(db.String(128), nullable=True)
    event_hash = db.Column(db.String(128), nullable=False)
    hmac_signature = db.Column(db.String(128), nullable=False)

    __table_args__ = (
        Index("ix_audit_event_type_time", "event_type", "created_at"),
        Index("ix_audit_user_time", "user_id", "created_at"),
    )


class AuditDataChange(db.Model):
    __tablename__ = "audit_data_changes"

    id = db.Column(UUID(as_uuid=False), primary_key=True, default=default_uuid)
    event_id = db.Column(UUID(as_uuid=False), db.ForeignKey("audit_events.id", ondelete="CASCADE"), nullable=False, index=True)
    table_name = db.Column(db.String(255), nullable=False, index=True)
    row_pk = db.Column(db.String(128), nullable=False, index=True)
    operation = db.Column(db.String(16), nullable=False)  # insert | update | delete
    before_data = db.Column(JSONB, nullable=True)
    after_data = db.Column(JSONB, nullable=True)

    event = db.relationship("AuditEvent", backref=db.backref("data_changes", cascade="all, delete-orphan"))

    __table_args__ = (
        Index("ix_audit_change_table_time", "table_name", "operation"),
    )


class AuditChainState(db.Model):
    __tablename__ = "audit_chain_state"

    id = db.Column(db.Integer, primary_key=True)
    last_event_id = db.Column(UUID(as_uuid=False), nullable=True)
    last_hash = db.Column(db.String(128), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("id", name="uq_audit_chain_state_singleton"),
    )

