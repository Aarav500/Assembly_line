from datetime import datetime, timedelta
import os
import requests
from sqlalchemy import func
from models import Event, AlertRule, Alert
from db import SessionLocal


def compute_metrics(session, window_minutes: int):
    now = datetime.utcnow()
    since = now - timedelta(minutes=window_minutes)

    # Counts
    visits = session.query(func.count(Event.id)).filter(Event.type == "visit", Event.created_at >= since).scalar() or 0
    signups = session.query(func.count(Event.id)).filter(Event.type == "signup", Event.created_at >= since).scalar() or 0

    # Revenue: sum of purchase amounts
    revenue = session.query(func.coalesce(func.sum(Event.amount), 0.0)).filter(Event.type == "purchase", Event.created_at >= since).scalar() or 0.0

    conversion_rate = 0.0
    if visits > 0:
        conversion_rate = signups / float(visits)

    return {
        "since": since.isoformat() + "Z",
        "until": now.isoformat() + "Z",
        "visits": int(visits),
        "signups": int(signups),
        "revenue": float(revenue),
        "conversion_rate": float(conversion_rate),
    }


def compare(value: float, comparator: str, threshold: float) -> bool:
    if comparator == "gt":
        return value > threshold
    if comparator == "lt":
        return value < threshold
    if comparator == "gte":
        return value >= threshold
    if comparator == "lte":
        return value <= threshold
    if comparator == "eq":
        return value == threshold
    if comparator == "neq":
        return value != threshold
    return False


def value_for_metric(metrics: dict, metric: str) -> float:
    if metric == "revenue":
        return float(metrics.get("revenue", 0.0))
    if metric == "conversion_rate":
        return float(metrics.get("conversion_rate", 0.0))
    if metric == "signups":
        return float(metrics.get("signups", 0))
    return 0.0


def send_alert_message(rule: AlertRule, metric_value: float, metrics: dict):
    message = (
        f"ALERT: '{rule.name}' triggered. Metric={rule.metric} value={metric_value} "
        f"comparator={rule.comparator} threshold={rule.threshold} window_minutes={rule.window_minutes}. "
        f"Window: {metrics.get('since')} to {metrics.get('until')}"
    )

    delivered = []
    channels = AlertRule.deserialize_channels(rule.channels_json)
    for ch in channels:
        ctype = (ch.get("type") or "").lower()
        if ctype == "console":
            print(message)
            delivered.append({"type": "console", "status": "ok"})
        elif ctype == "webhook":
            url = ch.get("url")
            if not url:
                delivered.append({"type": "webhook", "status": "error", "error": "missing url"})
                continue
            payload = {
                "text": message,
                "rule": rule.to_dict(),
                "metric_value": metric_value,
                "metrics": metrics,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            try:
                timeout = float(os.environ.get("ALERT_WEBHOOK_TIMEOUT", 4))
                resp = requests.post(url, json=payload, timeout=timeout)
                if 200 <= resp.status_code < 300:
                    delivered.append({"type": "webhook", "status": "ok", "status_code": resp.status_code})
                else:
                    delivered.append({"type": "webhook", "status": "error", "status_code": resp.status_code, "body": resp.text[:200]})
            except Exception as e:
                delivered.append({"type": "webhook", "status": "error", "error": str(e)})
        else:
            delivered.append({"type": ctype or "unknown", "status": "skipped"})

    return message, delivered


def evaluate_rules(session=None):
    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True

    results = []
    try:
        rules = session.query(AlertRule).filter(AlertRule.is_active == True).all()  # noqa: E712
        now = datetime.utcnow()
        for rule in rules:
            metrics = compute_metrics(session, rule.window_minutes)
            value = value_for_metric(metrics, rule.metric)
            should_trigger = compare(value, rule.comparator, rule.threshold)

            # Cooldown check
            can_trigger = True
            if rule.last_triggered_at is not None and rule.cool_down_minutes is not None:
                next_allowed = rule.last_triggered_at + timedelta(minutes=rule.cool_down_minutes)
                if now < next_allowed:
                    can_trigger = False

            triggered = False
            alert_obj = None
            if should_trigger and can_trigger:
                message, delivered = send_alert_message(rule, value, metrics)
                alert_obj = Alert(
                    rule_id=rule.id,
                    metric_value=value,
                    message=message,
                    delivered_channels_json=Alert.serialize_delivered(delivered),
                    triggered_at=now,
                )
                session.add(alert_obj)
                rule.last_triggered_at = now
                session.add(rule)
                session.commit()
                triggered = True

            results.append({
                "rule_id": rule.id,
                "name": rule.name,
                "metric": rule.metric,
                "value": value,
                "comparator": rule.comparator,
                "threshold": rule.threshold,
                "window_minutes": rule.window_minutes,
                "should_trigger": should_trigger,
                "triggered": triggered,
                "alert_id": alert_obj.id if alert_obj else None,
            })
        return results
    except Exception:
        session.rollback()
        raise
    finally:
        if own_session:
            session.close()

