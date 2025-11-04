from flask import Blueprint, current_app, request
from routes.resources import _aggregate_resources
from services.cost_analyzer import analyze_resource

suggestions_bp = Blueprint("suggestions", __name__)


@suggestions_bp.get("/suggestions")
def get_suggestions():
    resources = _aggregate_resources()
    suggestions = []
    for r in resources:
        try:
            s = analyze_resource(r)
            if s:
                suggestions.append(s)
        except Exception as e:
            current_app.logger.exception("Analyze failed for %s: %s", r.get("id"), e)

    # Filtering
    params = request.args
    action = params.get("action")
    min_savings = params.get("min_savings_monthly")
    provider = params.get("provider")
    env_tag = params.get("env")

    def _match(s):
        if action and s.get("action") != action:
            return False
        if provider and s.get("provider") != provider:
            return False
        if env_tag:
            if env_tag != (s.get("resource", {}).get("tags", {}).get("env")):
                return False
        if min_savings:
            try:
                if s.get("estimated_monthly_savings", 0.0) < float(min_savings):
                    return False
            except ValueError:
                pass
        return True

    filtered = [s for s in suggestions if _match(s)]
    total_monthly_savings = sum(s.get("estimated_monthly_savings", 0.0) for s in filtered)
    return {"count": len(filtered), "total_monthly_savings": round(total_monthly_savings, 2), "suggestions": filtered}

