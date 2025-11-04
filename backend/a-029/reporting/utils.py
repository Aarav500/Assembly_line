import re
from datetime import datetime
from typing import Any, Dict, List


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\-\_]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-_") or "report"


def _ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def format_currency(amount, currency="USD") -> str:
    if amount is None:
        return "-"
    try:
        amt = float(amount)
    except Exception:
        return str(amount)
    symbol = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "INR": "₹",
    }.get((currency or "").upper(), "")
    return f"{symbol}{amt:,.2f} {currency.upper()}".strip()


def percent(val) -> str:
    if val is None:
        return "-"
    try:
        v = float(val)
        if v > 1.0:
            return f"{v:.0f}%"
        return f"{v * 100:.0f}%"
    except Exception:
        return str(val)


def iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def with_defaults(data: Dict[str, Any]) -> Dict[str, Any]:
    project = data.get("project") or {}
    analysis = data.get("analysis") or {}
    timeline = project.get("timeline") or {}

    project.setdefault("name", "Untitled Project")
    project.setdefault("description", "")
    project.setdefault("owner", "")
    project.setdefault("status", "")
    project.setdefault("stakeholders", _ensure_list(project.get("stakeholders") or []))

    timeline.setdefault("start_date", "")
    timeline.setdefault("end_date", "")
    timeline.setdefault("milestones", _ensure_list(timeline.get("milestones") or []))
    project["timeline"] = timeline

    analysis.setdefault("summary", "")
    analysis.setdefault("key_findings", _ensure_list(analysis.get("key_findings") or []))

    metrics = analysis.get("metrics") or {}
    budget = metrics.get("budget") or {}
    progress = metrics.get("progress") or {}
    risks = _ensure_list(metrics.get("risks") or [])
    issues = _ensure_list(metrics.get("issues") or [])

    budget.setdefault("planned", None)
    budget.setdefault("actual", None)
    budget.setdefault("currency", "USD")
    progress.setdefault("percent_complete", 0)

    metrics["budget"] = budget
    metrics["progress"] = progress
    metrics["risks"] = risks
    metrics["issues"] = issues

    analysis["metrics"] = metrics

    data["project"] = project
    data["analysis"] = analysis

    data.setdefault("generated_for", "Stakeholders")
    data.setdefault("generated_by", "System")
    data.setdefault("generated_at", data.get("generated_at") or iso_now())

    return data

