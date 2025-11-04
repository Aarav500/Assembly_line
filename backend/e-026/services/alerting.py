from typing import Dict, Optional


def suggestion_to_alert(suggestion: Dict, thresholds: Dict) -> Optional[Dict]:
    if not suggestion:
        return None

    action = suggestion.get("action")
    if action == "rightsizing_not_needed":
        return None

    savings = float(suggestion.get("estimated_monthly_savings", 0.0))
    idle_hours = float(((suggestion.get("metrics") or {}).get("idle_hours_7d", 0.0)))

    severity = "info"
    title = ""
    if action == "terminate":
        title = "Idle resource candidate for termination"
        severity = "high" if savings >= thresholds.get("high_savings_threshold", 200.0) else "medium"
    elif action == "downsize":
        title = "Rightsizing opportunity: downsize"
        if savings >= thresholds.get("high_savings_threshold", 200.0):
            severity = "high"
        elif savings >= thresholds.get("savings_alert_threshold", 50.0):
            severity = "medium"
        else:
            severity = "low"
    elif action == "upsize":
        title = "Performance risk: consider upsizing"
        severity = "medium" if savings < 0 else "low"  # negative savings => additional cost

    if action in ("downsize", "terminate"):
        min_savings = thresholds.get("savings_alert_threshold", 50.0)
        if savings < min_savings and action != "terminate":
            # Skip low-value downsizing alerts
            return None

    if action == "terminate" and idle_hours < thresholds.get("idle_hours_threshold", 140):
        # Skip if idle not long enough
        return None

    alert = {
        "resource_id": suggestion.get("resource_id"),
        "resource_name": suggestion.get("resource_name"),
        "provider": suggestion.get("provider"),
        "region": suggestion.get("region"),
        "severity": severity,
        "action": action,
        "title": title,
        "message": suggestion.get("rationale"),
        "estimated_monthly_savings": suggestion.get("estimated_monthly_savings"),
        "recommended_type": suggestion.get("recommended_type"),
        "metrics": suggestion.get("metrics", {}),
    }
    return alert

