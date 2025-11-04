from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from models import Experiment, Variant, Assignment, Event
from typing import Dict, Any
import math


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def z_test_proportions(p1, n1, p2, n2):
    if n1 == 0 or n2 == 0:
        return {"z": None, "p_value": None}
    pooled = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return {"z": None, "p_value": None}
    z = (p1 - p2) / se
    p = 2 * (1 - normal_cdf(abs(z)))
    return {"z": z, "p_value": p}


def proportion_ci(p, n, z=1.96):
    if n == 0:
        return [None, None]
    se = math.sqrt(p * (1 - p) / n)
    return [max(0.0, p - z * se), min(1.0, p + z * se)]


def analyze_experiment(db: Session, experiment_id: int) -> Dict[str, Any]:
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise ValueError("Experiment not found")

    variants = db.query(Variant).filter(Variant.experiment_id == experiment_id).all()
    if not variants:
        return {
            "experiment": {"id": experiment_id, "name": None, "metric_name": None, "status": None},
            "variants": [],
            "comparisons_vs_control": [],
            "control_variant_id": None,
        }

    control = None
    for v in variants:
        if v.name.lower() in ("control", "a", "baseline"):
            control = v
            break
    if control is None:
        control = variants[0]

    assigned_counts = dict(
        db.query(Assignment.variant_id, func.count(Assignment.id))
        .filter(Assignment.experiment_id == experiment_id)
        .group_by(Assignment.variant_id)
        .all()
    )

    conv_rows = (
        db.query(Event.variant_id, func.count(func.distinct(Event.user_id)))
        .filter(Event.experiment_id == experiment_id, Event.event_name == exp.metric_name)
        .group_by(Event.variant_id)
        .all()
    )
    conversions = dict(conv_rows)

    val_rows = (
        db.query(Event.variant_id, func.avg(Event.value), func.sum(Event.value), func.count(Event.id))
        .filter(Event.experiment_id == experiment_id, Event.event_name == exp.metric_name)
        .group_by(Event.variant_id)
        .all()
    )
    avg_value = {vid: avg for vid, avg, sumv, cnt in val_rows}
    sum_value = {vid: sumv for vid, avg, sumv, cnt in val_rows}
    event_count = {vid: cnt for vid, avg, sumv, cnt in val_rows}

    results = []
    control_stats = None
    for v in variants:
        n = int(assigned_counts.get(v.id, 0))
        x = int(conversions.get(v.id, 0))
        rate = x / n if n > 0 else 0.0
        ci = proportion_ci(rate, n)
        stats = {
            "variant_id": v.id,
            "variant_name": v.name,
            "assigned": n,
            "conversions": x,
            "conversion_rate": rate,
            "conversion_rate_ci95": ci,
            "avg_value": avg_value.get(v.id),
            "sum_value": sum_value.get(v.id, 0.0),
            "event_count": int(event_count.get(v.id, 0)),
            "allocation": v.allocation,
        }
        if v.id == control.id:
            control_stats = stats
        results.append(stats)

    comparisons = []
    if control_stats:
        p2 = control_stats["conversion_rate"]
        n2 = control_stats["assigned"]
        for st in results:
            if st["variant_id"] == control.id:
                continue
            p1 = st["conversion_rate"]
            n1 = st["assigned"]
            test = z_test_proportions(p1, n1, p2, n2)
            uplift = p1 - p2
            rel = (p1 / p2 - 1.0) if p2 > 0 else None
            comparisons.append(
                {
                    "variant_id": st["variant_id"],
                    "variant_name": st["variant_name"],
                    "uplift_absolute": uplift,
                    "uplift_relative": rel,
                    "z": test["z"],
                    "p_value": test["p_value"],
                }
            )

    return {
        "experiment": {"id": exp.id, "name": exp.name, "metric_name": exp.metric_name, "status": exp.status},
        "variants": results,
        "comparisons_vs_control": comparisons,
        "control_variant_id": control.id if control else None,
    }

