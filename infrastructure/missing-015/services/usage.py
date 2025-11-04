import calendar
import datetime as dt
from storage.redis_client import get_redis
from services.alerts import send_quota_alert
from services.billing import bill_overage_increment


def month_slug(now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.utcnow()
    return now.strftime("%Y-%m")


def month_end_ts(now: dt.datetime | None = None) -> int:
    now = now or dt.datetime.utcnow()
    last_day = calendar.monthrange(now.year, now.month)[1]
    end_dt = dt.datetime(now.year, now.month, last_day, 23, 59, 59)
    return int(end_dt.timestamp())


def usage_key(user_id: str, month: str | None = None) -> str:
    month = month or month_slug()
    return f"usage:{user_id}:{month}"


def billed_key(user_id: str, month: str | None = None) -> str:
    month = month or month_slug()
    return f"billing:billed:{user_id}:{month}"


def alert_key(user_id: str, month: str | None = None) -> str:
    month = month or month_slug()
    return f"alerted:{user_id}:{month}"


def get_usage(user_id: str, month: str | None = None) -> int:
    r = get_redis()
    val = r.get(usage_key(user_id, month))
    return int(val) if val else 0


def get_billed_overage(user_id: str, month: str | None = None) -> int:
    r = get_redis()
    val = r.get(billed_key(user_id, month))
    return int(val) if val else 0


def precheck_hard_quota(user_id: str, tier: dict) -> tuple[bool, dict]:
    """Return allowed flag and headers related to quota."""
    quota = int(tier.get("monthly_quota") or 0)
    hard = bool(int(tier.get("hard_limit") or 0))
    current = get_usage(user_id)
    headers = {
        "X-Quota-Limit-Month": str(quota) if quota else "0",
        "X-Quota-Used-Month": str(current),
        "X-Quota-Remaining-Month": str(max(0, quota - current)) if quota else "0",
    }
    if hard and quota and current >= quota:
        return False, headers
    return True, headers


def increment_and_handle(user: dict, tier: dict) -> dict:
    """Increment usage after successful request, send alerts, and bill overage."""
    r = get_redis()
    uid = user["id"]
    month = month_slug()
    ukey = usage_key(uid, month)
    # Increment usage
    new_total = r.incr(ukey, 1)
    # Persist per-month histories; optional: set expiry in the future (e.g., 18 months)
    # r.expire(ukey, 60*60*24*31*18)

    out = {
        "month": month,
        "usage": new_total,
    }

    quota = int(tier.get("monthly_quota") or 0)
    out["quota"] = quota
    if quota > 0:
        remaining = max(0, quota - new_total)
        out["remaining"] = remaining
        _handle_alerts(user, tier, new_total, quota)
        _handle_billing(user, tier, new_total, quota)
    return out


def _handle_alerts(user: dict, tier: dict, usage: int, quota: int):
    if quota <= 0:
        return
    r = get_redis()
    uid = user["id"]
    month = month_slug()
    akey = alert_key(uid, month)
    last_stage = r.get(akey)
    last_stage = int(last_stage) if last_stage else 0

    stages = [80, 95, 100]
    pct = int((usage / quota) * 100)
    for stage in stages:
        if pct >= stage and last_stage < stage:
            # send alert and update last_stage
            try:
                send_quota_alert(user, tier, stage, usage, quota)
            finally:
                r.set(akey, stage)


def _handle_billing(user: dict, tier: dict, usage: int, quota: int):
    if quota <= 0:
        return
    if usage <= quota:
        return
    r = get_redis()
    uid = user["id"]
    month = month_slug()
    bkey = billed_key(uid, month)
    already_billed = get_billed_overage(uid, month)
    overage_units = usage - quota
    delta = overage_units - already_billed
    if delta <= 0:
        return
    price = float(tier.get("overage_price") or 0.0)
    currency = tier.get("currency") or "USD"
    billed = bill_overage_increment(user, month, delta, price, currency)
    if billed:
        r.incrby(bkey, delta)

