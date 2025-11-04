from typing import Dict, Any


def safe_ratio(canary: float, baseline: float) -> float:
    if baseline == 0:
        if canary == 0:
            return 1.0
        return float("inf")
    return canary / baseline


def evaluate_rule(baseline_value: float, canary_value: float, rule: Dict[str, Any]) -> Dict[str, Any]:
    comparator = (rule.get("comparator") or "ratio").lower()
    min_v = rule.get("min")
    max_v = rule.get("max")

    result = {
        "passed": True,
        "reason": "",
        "comparator": comparator,
        "min": min_v,
        "max": max_v,
        "ratio": None,
        "delta": None,
    }

    if comparator == "ratio":
        r = safe_ratio(canary_value, baseline_value)
        result["ratio"] = r
        reasons = []
        if min_v is not None and r < float(min_v):
            result["passed"] = False
            reasons.append(f"ratio {r:.6g} < min {float(min_v):.6g}")
        if max_v is not None and r > float(max_v):
            result["passed"] = False
            reasons.append(f"ratio {r:.6g} > max {float(max_v):.6g}")
        if not reasons:
            reasons.append("ratio within bounds")
        result["reason"] = "; ".join(reasons)
        return result

    if comparator == "delta":
        d = canary_value - baseline_value
        result["delta"] = d
        reasons = []
        if min_v is not None and d < float(min_v):
            result["passed"] = False
            reasons.append(f"delta {d:.6g} < min {float(min_v):.6g}")
        if max_v is not None and d > float(max_v):
            result["passed"] = False
            reasons.append(f"delta {d:.6g} > max {float(max_v):.6g}")
        if not reasons:
            reasons.append("delta within bounds")
        result["reason"] = "; ".join(reasons)
        return result

    if comparator == "absolute":
        v = canary_value
        reasons = []
        if min_v is not None and v < float(min_v):
            result["passed"] = False
            reasons.append(f"value {v:.6g} < min {float(min_v):.6g}")
        if max_v is not None and v > float(max_v):
            result["passed"] = False
            reasons.append(f"value {v:.6g} > max {float(max_v):.6g}")
        if not reasons:
            reasons.append("value within bounds")
        result["reason"] = "; ".join(reasons)
        return result

    raise ValueError(f"unsupported comparator: {comparator}")

