import os
import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Migration(Base):
    __tablename__ = "migrations"
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(String(128), nullable=True)
    target_env = Column(String(32), nullable=False)
    sql = Column(Text, nullable=False)

    status = Column(String(32), default="pending_review")  # pending_review|blocked|needs_approval|approved|applied|failed
    issues = Column(Text, nullable=True)  # JSON-encoded list

    dry_run_status = Column(String(32), default=None)  # success|failed
    dry_run_log = Column(Text, nullable=True)

    apply_status = Column(String(32), default=None)  # success|failed
    apply_log = Column(Text, nullable=True)
    applied_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    approvals = relationship("Approval", back_populates="migration", cascade="all, delete-orphan")

    def set_issues(self, issues_list):
        self.issues = json.dumps(issues_list or [])

    def get_issues(self):
        try:
            return json.loads(self.issues) if self.issues else []
        except Exception:
            return []

    def to_dict(self, include_sql=True, include_approvals=True):
        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "created_by": self.created_by,
            "target_env": self.target_env,
            "status": self.status,
            "issues": self.get_issues(),
            "dry_run_status": self.dry_run_status,
            "dry_run_log": self.dry_run_log,
            "apply_status": self.apply_status,
            "apply_log": self.apply_log,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_sql:
            data["sql"] = self.sql
        if include_approvals:
            data["approvals"] = [a.to_dict() for a in self.approvals]
        return data

    def sql_file_path(self):
        folder = os.path.join(os.getcwd(), "migration_store")
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, f"migration_{self.id}.sql")

class Approval(Base):
    __tablename__ = "approvals"
    id = Column(Integer, primary_key=True)
    migration_id = Column(Integer, ForeignKey("migrations.id", ondelete="CASCADE"), nullable=False)
    user = Column(String(128), nullable=False)
    role = Column(String(64), nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    migration = relationship("Migration", back_populates="approvals")

    def to_dict(self):
        return {
            "id": self.id,
            "migration_id": self.migration_id,
            "user": self.user,
            "role": self.role,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

Index("ix_approvals_mig_role_user", Approval.migration_id, Approval.role, Approval.user, unique=True)

