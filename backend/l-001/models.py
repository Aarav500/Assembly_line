from datetime import datetime
from decimal import Decimal
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from database import db


class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)

    projects = db.relationship("Project", backref="team", cascade="all, delete-orphan")
    ledger_entries = db.relationship("LedgerEntry", backref="team", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
        }


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)

    ledger_entries = db.relationship("LedgerEntry", backref="project", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("team_id", "name", name="uq_project_name_per_team"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "team_id": self.team_id,
        }


class ModelDef(db.Model):
    __tablename__ = "models"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    provider = db.Column(db.String(255), nullable=True)
    input_cost_per_1k = db.Column(db.Numeric(20, 8), nullable=False)
    output_cost_per_1k = db.Column(db.Numeric(20, 8), nullable=False)
    currency = db.Column(db.String(16), nullable=False, default="USD")

    ledger_entries = db.relationship("LedgerEntry", backref="model", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "input_cost_per_1k": float(self.input_cost_per_1k),
            "output_cost_per_1k": float(self.output_cost_per_1k),
            "currency": self.currency,
        }


class LedgerEntry(db.Model):
    __tablename__ = "ledger_entries"

    id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.DateTime, default=datetime.utcnow, index=True, nullable=False)

    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    model_id = db.Column(db.Integer, db.ForeignKey("models.id"), nullable=False)

    input_tokens = db.Column(db.Integer, default=0, nullable=False)
    output_tokens = db.Column(db.Integer, default=0, nullable=False)
    total_tokens = db.Column(db.Integer, default=0, nullable=False)

    input_cost = db.Column(db.Numeric(20, 8), default=Decimal(0), nullable=False)
    output_cost = db.Column(db.Numeric(20, 8), default=Decimal(0), nullable=False)
    total_cost = db.Column(db.Numeric(20, 8), default=Decimal(0), nullable=False)

    currency = db.Column(db.String(16), nullable=False, default="USD")

    user = db.Column(db.String(255), nullable=True)
    note = db.Column(db.String(1024), nullable=True)
    metadata = db.Column(SQLITE_JSON, nullable=True)
    tags = db.Column(db.String(255), nullable=True)  # comma-separated tags

    def to_dict(self):
        return {
            "id": self.id,
            "ts": self.ts.isoformat() + "Z",
            "team_id": self.team_id,
            "project_id": self.project_id,
            "model_id": self.model_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "input_cost": float(self.input_cost),
            "output_cost": float(self.output_cost),
            "total_cost": float(self.total_cost),
            "currency": self.currency,
            "user": self.user,
            "note": self.note,
            "metadata": self.metadata,
            "tags": self.tags.split(",") if self.tags else [],
        }

