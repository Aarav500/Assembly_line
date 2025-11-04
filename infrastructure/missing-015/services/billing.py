import os
import requests

BILLING_WEBHOOK_URL = os.getenv("BILLING_WEBHOOK_URL")


def bill_overage_increment(user: dict, month: str, units: int, price_per_unit: float, currency: str = "USD") -> bool:
    if units <= 0:
        return True
    if not BILLING_WEBHOOK_URL:
        # No external billing configured; simulate success
        return True
    payload = {
        "type": "overage_charge",
        "user": {
            "id": user.get("id"),
            "email": user.get("email"),
            "billing_id": user.get("billing_id"),
            "tier": user.get("tier"),
        },
        "period": month,
        "units": units,
        "unit_price": price_per_unit,
        "currency": currency,
        "amount": round(units * price_per_unit, 4),
        "description": f"API overage {units} requests in {month} at {price_per_unit} {currency}/request"
    }
    try:
        resp = requests.post(BILLING_WEBHOOK_URL, json=payload, timeout=8)
        return 200 <= resp.status_code < 300
    except Exception:
        return False

