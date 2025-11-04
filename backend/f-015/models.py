from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import json
from database import Base


class Experiment(Base):
    __tablename__ = "experiments"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(50), default="active")
    metric_name = Column(String(128), default="purchase")
    created_at = Column(DateTime, server_default=func.now())

    variants = relationship("Variant", back_populates="experiment", cascade="all, delete-orphan")


class Variant(Base):
    __tablename__ = "variants"
    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    allocation = Column(Float, nullable=False, default=0.0)
    params_json = Column(Text, nullable=True)

    experiment = relationship("Experiment", back_populates="variants")
    assignments = relationship("Assignment", back_populates="variant")

    __table_args__ = (
        UniqueConstraint("experiment_id", "name", name="uq_variant_name_per_experiment"),
    )

    @property
    def params(self):
        if self.params_json:
            try:
                return json.loads(self.params_json)
            except Exception:
                return {}
        return {}

    @params.setter
    def params(self, value):
        self.params_json = json.dumps(value or {})


class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("variants.id"), nullable=False, index=True)
    user_id = Column(String(255), nullable=False)
    assigned_at = Column(DateTime, server_default=func.now())

    variant = relationship("Variant", back_populates="assignments")

    __table_args__ = (
        UniqueConstraint("experiment_id", "user_id", name="uq_assignment_unique"),
        Index("idx_assign_experiment_variant", "experiment_id", "variant_id"),
    )


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("variants.id"), nullable=True, index=True)
    event_name = Column(String(255), nullable=False, index=True)
    value = Column(Float, nullable=True)
    ts = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_event_exp_user_name", "experiment_id", "user_id", "event_name"),
    )

