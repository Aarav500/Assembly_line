from flask import Blueprint, current_app
from routes.resources import _aggregate_resources
from services.cost_analyzer import analyze_resource
from services.alerting import suggestion_to_alert

alerts_bp = Blueprint("alerts", __name__)


@alerts_bp.get("/alerts")
def get_alerts():
    resources = _aggregate_resources()
    alerts = []
    for r in resources:
        try:
            s = analyze_resource(r)
            if s:
                alert = suggestion_to_alert(s, thresholds={
                    "savings_alert_threshold": current_app.config.get("SAVINGS_ALERT_THRESHOLD", 50.0),
                    "high_savings_threshold": current_app.config.get("HIGH_SAVINGS_THRESHOLD", 200.0),
                    "idle_hours_threshold": current_app.config.get("IDLE_HOURS_THRESHOLD", 140),
                })
                if alert:
                    alerts.append(alert)
        except Exception as e:
            current_app.logger.exception("Alert generation failed for %s: %s", r.get("id"), e)

    return {"count": len(alerts), "alerts": alerts}

