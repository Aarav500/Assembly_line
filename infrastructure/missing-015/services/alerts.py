import os
import json
import requests

ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL")


def send_quota_alert(user: dict, tier: dict, stage: int, usage: int, quota: int) -> bool:
    if not ALERT_WEBHOOK_URL:
        return False
    payload = {
        "type": "quota_alert",
        "stage": stage,
        "user": {
            "id": user.get("id"),
            "email": user.get("email"),
            "tier": user.get("tier"),
        },
        "tier": tier.get("name"),
        "usage": usage,
        "quota": quota,
        "message": f"User {user.get('id')} reached {stage}% of monthly quota ({usage}/{quota})"
    }
    try:
        resp = requests.post(ALERT_WEBHOOK_URL, json=payload, timeout=5)
        return 200 <= resp.status_code < 300
    except Exception:
        return False

