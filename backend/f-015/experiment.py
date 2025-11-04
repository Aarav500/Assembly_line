from sqlalchemy.orm import Session
from models import Experiment, Variant, Assignment, Event
import hashlib
import os
from typing import Dict, List, Optional

SALT = os.getenv("AB_SALT", "default_salt")


class ExperimentManager:
    def __init__(self, db: Session):
        self.db = db

    def create_experiment(self, name: str, metric_name: str, variants: List[Dict]):
        existing = self.db.query(Experiment).filter(Experiment.name == name).first()
        if existing:
            return existing
        exp = Experiment(name=name, metric_name=metric_name or "purchase", status="active")
        self.db.add(exp)
        self.db.flush()
        total_alloc = sum(float(v.get("allocation", 0.0)) for v in variants)
        if total_alloc <= 0:
            raise ValueError("Total allocation must be > 0")
        for v in variants:
            alloc = float(v.get("allocation", 0.0)) / total_alloc
            var = Variant(experiment_id=exp.id, name=v["name"], allocation=alloc)
            if "params" in v:
                var.params = v["params"]
            self.db.add(var)
        self.db.commit()
        self.db.refresh(exp)
        return exp

    def get_experiment_by_id(self, experiment_id: int) -> Optional[Experiment]:
        return self.db.query(Experiment).filter(Experiment.id == experiment_id).first()

    def get_experiment_by_name(self, name: str) -> Optional[Experiment]:
        return self.db.query(Experiment).filter(Experiment.name == name).first()

    def variant_bins(self, experiment: Experiment):
        variants = (
            self.db.query(Variant)
            .filter(Variant.experiment_id == experiment.id)
            .order_by(Variant.id.asc())
            .all()
        )
        cumsum = 0.0
        bins = []
        for v in variants:
            cumsum += v.allocation
            bins.append((v, cumsum))
        if bins:
            bins[-1] = (bins[-1][0], 1.0)
        return bins

    def assign_user(self, experiment: Experiment, user_id: str) -> Variant:
        existing = (
            self.db.query(Assignment)
            .filter(Assignment.experiment_id == experiment.id, Assignment.user_id == user_id)
            .first()
        )
        if existing:
            return self.db.query(Variant).get(existing.variant_id)
        bins = self.variant_bins(experiment)
        if not bins:
            raise ValueError("Experiment has no variants")
        h = hashlib.sha1(f"{SALT}:{experiment.id}:{user_id}".encode("utf-8")).hexdigest()
        val = int(h[:15], 16) / float(16**15)
        chosen = None
        for v, upper in bins:
            if val <= upper:
                chosen = v
                break
        if chosen is None:
            chosen = bins[-1][0]
        assignment = Assignment(experiment_id=experiment.id, user_id=user_id, variant_id=chosen.id)
        self.db.add(assignment)
        self.db.commit()
        return chosen

    def track_event(self, experiment: Experiment, user_id: str, event_name: str, value: Optional[float] = None, variant: Optional[Variant] = None):
        if variant is None:
            assign = (
                self.db.query(Assignment)
                .filter(Assignment.experiment_id == experiment.id, Assignment.user_id == user_id)
                .first()
            )
            variant_id = assign.variant_id if assign else None
        else:
            variant_id = variant.id
        evt = Event(
            experiment_id=experiment.id,
            user_id=user_id,
            variant_id=variant_id,
            event_name=event_name,
            value=value,
        )
        self.db.add(evt)
        self.db.commit()
        return evt

