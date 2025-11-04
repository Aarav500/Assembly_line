from sqlalchemy.orm import Session
from experiment import ExperimentManager
from models import Variant
import random
import math
from typing import Dict, Optional


def clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def run_simulation(db: Session, spec: Dict, seed: Optional[int] = None):
    rng = random.Random(seed or 1234)
    mgr = ExperimentManager(db)

    exp = None
    if "experiment_id" in spec and spec["experiment_id"]:
        exp = mgr.get_experiment_by_id(int(spec["experiment_id"]))
        if not exp:
            raise ValueError("experiment_id not found")
    else:
        e = spec.get("experiment") or {}
        name = e.get("name", f"synth_exp_{rng.randint(1000,9999)}")
        metric = e.get("metric_name", "purchase")
        variants = e.get("variants") or [
            {"name": "control", "allocation": 0.5},
            {"name": "b", "allocation": 0.5},
        ]
        exp = mgr.create_experiment(name=name, metric_name=metric, variants=variants)

    effects = spec.get("effects", {})
    base = spec.get(
        "base",
        {"click": 0.2, "purchase": 0.05, "revenue_mean": 50.0, "revenue_sd": 10.0},
    )
    users = int(spec.get("users", 1000))

    summary = {}
    for v in db.query(Variant).filter(Variant.experiment_id == exp.id).all():
        summary[v.name] = {"assigned": 0, "clicks": 0, "purchases": 0, "revenue": 0.0}

    for i in range(users):
        user_id = f"synth_{seed or 0}_{i}"
        variant = mgr.assign_user(exp, user_id)
        summary[variant.name]["assigned"] += 1

        eff = effects.get(variant.name, {})
        p_click = clip01(float(base.get("click", 0.2)) * (1 + float(eff.get("click", 0.0))))
        p_purchase = clip01(float(base.get("purchase", 0.05)) * (1 + float(eff.get("purchase", 0.0))))

        mgr.track_event(exp, user_id, "view", value=None, variant=variant)

        if rng.random() < p_click:
            summary[variant.name]["clicks"] += 1
            mgr.track_event(exp, user_id, "click", value=None, variant=variant)

        if rng.random() < p_purchase:
            rev_mean = float(base.get("revenue_mean", 50.0)) * (1 + float(eff.get("revenue", 0.0)))
            rev_sd = float(base.get("revenue_sd", 10.0))
            mu = math.log(max(1e-6, rev_mean)) - 0.5
            sigma = max(0.05, min(1.0, rev_sd / max(1.0, rev_mean)))
            revenue = math.exp(rng.gauss(mu, sigma))
            summary[variant.name]["purchases"] += 1
            summary[variant.name]["revenue"] += revenue
            mgr.track_event(exp, user_id, exp.metric_name, value=revenue, variant=variant)

    return {"experiment_id": exp.id, "experiment_name": exp.name, "summary": summary}

