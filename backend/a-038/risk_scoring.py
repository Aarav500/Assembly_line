import math
from typing import Dict, Any, List, Tuple, Optional
from utils import clamp


DEFAULT_WEIGHTS = {
    "technical_debt": 0.35,
    "dependencies": 0.30,
    "backups": 0.20,
    "ci": 0.15,
}


def score_technical_debt(metrics: Dict[str, Any]) -> Tuple[Optional[float], Dict[str, Any]]:
    # Allow override
    if isinstance(metrics, dict) and ("debt_score" in metrics) and metrics.get("debt_score") is not None:
        try:
            ds = float(metrics.get("debt_score"))
            return clamp(ds, 0, 100), {"method": "override", "inputs": metrics}
        except Exception:
            pass

    linter_issues = float(metrics.get("linter_issues", 0) or 0)
    todo_count = float(metrics.get("todo_count", 0) or 0)
    test_coverage = metrics.get("test_coverage")
    complexity = metrics.get("complexity")

    # Normalize to 0..1 risk contributions
    # Coverage: 80% -> 0 risk, 0% -> 1 risk, >80% -> 0
    if test_coverage is None:
        coverage_risk = 0.5
    else:
        try:
            cov = float(test_coverage)
        except Exception:
            cov = 0.0
        coverage_risk = clamp((80.0 - cov) / 80.0, 0.0, 1.0)

    # Linter issues: saturating exponential (100 issues ~ 63% risk)
    linter_risk = 1.0 - math.exp(-max(0.0, linter_issues) / 100.0)

    # TODOs: saturating exponential (50 TODOs ~ 63% risk)
    todo_risk = 1.0 - math.exp(-max(0.0, todo_count) / 50.0)

    # Complexity: thresholded linear (10 baseline, 30 high)
    if complexity is None:
        complexity_risk = 0.3
    else:
        try:
            cx = float(complexity)
        except Exception:
            cx = 10.0
        complexity_risk = clamp((cx - 10.0) / 20.0, 0.0, 1.0)

    weights = {
        "coverage": 0.35,
        "linter": 0.25,
        "todos": 0.20,
        "complexity": 0.20,
    }

    combined = (
        coverage_risk * weights["coverage"]
        + linter_risk * weights["linter"]
        + todo_risk * weights["todos"]
        + complexity_risk * weights["complexity"]
    )

    score = clamp(combined * 100.0, 0.0, 100.0)
    details = {
        "method": "computed",
        "weights": weights,
        "inputs": {
            "linter_issues": linter_issues,
            "todo_count": todo_count,
            "test_coverage": test_coverage,
            "complexity": complexity,
        },
        "normalized": {
            "coverage_risk": coverage_risk,
            "linter_risk": linter_risk,
            "todo_risk": todo_risk,
            "complexity_risk": complexity_risk,
        },
    }
    return score, details


def score_backups(backups: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    has_backups = bool(backups.get("has_backups", False))
    last_backup_days = backups.get("last_backup_days")
    tested_restore = bool(backups.get("tested_restore", False))

    if not has_backups:
        base = 90.0
    else:
        try:
            days = float(last_backup_days)
        except Exception:
            days = None
        if days is None:
            base = 40.0
        elif days <= 0:
            base = 10.0
        elif days <= 1:
            base = 15.0
        elif days <= 7:
            base = 30.0
        elif days <= 30:
            base = 60.0
        else:
            base = 80.0

    if has_backups and not tested_restore:
        base += 15.0

    score = clamp(base, 0.0, 100.0)
    details = {
        "inputs": backups,
        "base": base,
        "score": score,
    }
    return score, details


def score_ci(ci: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    has_ci = bool(ci.get("has_ci", False))
    status = str(ci.get("status", "unknown") or "unknown").lower()
    try:
        last_build_days = float(ci.get("last_build_days"))
    except Exception:
        last_build_days = None

    if not has_ci:
        base = 80.0
    else:
        if status == "passing":
            base = 10.0
        elif status == "failing":
            base = 60.0
        else:
            base = 30.0

        if last_build_days is not None:
            if last_build_days > 14:
                base += 20.0
            elif last_build_days > 7:
                base += 10.0

    score = clamp(base, 0.0, 100.0)
    details = {
        "inputs": ci,
        "score": score,
    }
    return score, details


def score_dependencies(analysis: List[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
    if not analysis:
        return 0.0, {"note": "no dependencies provided"}

    total = len(analysis)
    outdated_items = [p for p in analysis if p.get("is_outdated")]
    outdated = len(outdated_items)

    # Weighted by severity: major 3, minor 2, patch 1
    weights = {"major": 3, "minor": 2, "patch": 1, "unknown": 1}
    weighted_sum = 0
    for p in outdated_items:
        sever = p.get("severity") or "unknown"
        weighted_sum += weights.get(sever, 1)

    # Normalize by max possible weight (all outdated at major)
    max_weight = total * weights["major"] if total > 0 else 1
    ratio = weighted_sum / max_weight if max_weight else 0

    # Base risk as percentage
    risk = ratio * 100.0

    # If many errors (failed to fetch latest), slightly increase uncertainty
    error_count = len([p for p in analysis if p.get("latest_version") is None])
    if error_count > 0:
        risk += min(10.0, error_count * 1.5)

    score = clamp(risk, 0.0, 100.0)

    details = {
        "total": total,
        "outdated": outdated,
        "weighted_sum": weighted_sum,
        "max_weight": max_weight,
        "ratio": ratio,
        "score": score,
        "error_count": error_count,
    }
    return score, details


def aggregate_scores(components: Dict[str, Optional[float]] , weights: Dict[str, float] = None) -> Tuple[Optional[float], Dict[str, Any]]:
    weights = dict((weights or DEFAULT_WEIGHTS))

    # Use only provided components and renormalize weights
    available = {k: v for k, v in components.items() if v is not None}
    if not available:
        return None, {"weights": {}, "note": "no component scores available"}

    total_weight = sum(weights.get(k, 0.0) for k in available.keys())
    if total_weight <= 0:
        # fallback equal weights
        equal = 1.0 / len(available)
        norm_weights = {k: equal for k in available.keys()}
    else:
        norm_weights = {k: (weights.get(k, 0.0) / total_weight) for k in available.keys()}

    score = 0.0
    for k, v in available.items():
        score += float(v) * norm_weights[k]

    info = {
        "weights": norm_weights,
        "components": available,
    }
    return clamp(score, 0.0, 100.0), info


def grade_from_score(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    s = float(score)
    if s < 20:
        return "A (Low)"
    if s < 40:
        return "B (Moderate)"
    if s < 60:
        return "C (Elevated)"
    if s < 80:
        return "D (High)"
    return "E (Critical)"

