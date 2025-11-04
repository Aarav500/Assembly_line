from typing import Dict, Tuple


def _severity(abs_z: float, abs_pct: float) -> str:
    # simple rule-based severity
    if abs_z >= 5 or abs_pct >= 0.5:
        return "severe"
    if abs_z >= 4 or abs_pct >= 0.35:
        return "moderate"
    return "minor"


def detect_regressions(
    baseline: dict,
    observed_metrics: Dict[str, float],
    thresholds: Dict[str, float] | None = None,
) -> dict:
    if thresholds is None:
        thresholds = {}
    z_threshold = float(thresholds.get("z_threshold", 3.0))
    percent_threshold = float(thresholds.get("percent_threshold", 0.25))
    min_std = float(thresholds.get("min_std", 1e-6))
    eps_mean = 1e-12

    base_metrics = baseline.get("metrics", {})

    results = []
    regressions = []

    missing = []
    extra = []

    observed_keys = set(observed_metrics.keys())
    baseline_keys = set(base_metrics.keys())

    for name in sorted(baseline_keys):
        info = base_metrics[name]
        m = float(info.get("mean", 0.0))
        s = max(float(info.get("std", 1.0)), min_std)
        if name not in observed_metrics:
            missing.append(name)
            continue
        v = float(observed_metrics[name])
        delta = v - m
        pct = delta / (abs(m) + eps_mean)
        z = delta / s
        abs_z = abs(z)
        abs_pct = abs(pct)
        triggers = []
        is_reg = False
        if abs_z > z_threshold:
            is_reg = True
            triggers.append(f"z>{z_threshold}")
        if abs_pct > percent_threshold:
            is_reg = True
            triggers.append(f"pct>{percent_threshold}")
        item = {
            "name": name,
            "baseline_mean": m,
            "baseline_std": s,
            "observed": v,
            "delta": delta,
            "percent_change": pct,
            "z_score": z,
            "regression": is_reg,
            "reasons": triggers,
        }
        results.append(item)
        if is_reg:
            sev = _severity(abs_z, abs_pct)
            item["severity"] = sev
            regressions.append(item)

    for name in sorted(observed_keys - baseline_keys):
        extra.append(name)

    # summary
    total_metrics = len(baseline_keys)
    regressions_count = len(regressions)
    missing_count = len(missing)
    extra_count = len(extra)

    # grade heuristic
    if regressions_count == 0 and missing_count == 0:
        grade = "ok"
    elif regressions_count / max(total_metrics, 1) < 0.1 and missing_count == 0:
        grade = "warning"
    else:
        grade = "fail"

    # top regressions by worst of normalized scores
    def score(item):
        abs_z = abs(item.get("z_score", 0.0))
        abs_pct = abs(item.get("percent_change", 0.0))
        return max(abs_z, abs_pct / max(percent_threshold, 1e-12) * 3.0)

    top = sorted(regressions, key=score, reverse=True)[:20]

    summary = {
        "total_metrics": total_metrics,
        "regressions_count": regressions_count,
        "missing_count": missing_count,
        "extra_count": extra_count,
        "grade": grade,
    }

    return {
        "thresholds": {
            "z_threshold": z_threshold,
            "percent_threshold": percent_threshold,
            "min_std": min_std,
        },
        "summary": summary,
        "regressions": top,
        "missing": missing,
        "extra": extra,
    }

