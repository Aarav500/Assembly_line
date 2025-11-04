from storage.redis_client import get_redis


def get_tier(name: str) -> dict | None:
    r = get_redis()
    key = f"api:tier:{name}"
    data = r.hgetall(key)
    if not data:
        return None
    # Cast numeric fields
    for fld in ["rps", "rpm", "monthly_quota"]:
        if fld in data and data[fld] != "":
            data[fld] = int(data[fld])
        else:
            data[fld] = 0
    for fld in ["overage_price"]:
        if fld in data and data[fld] != "":
            data[fld] = float(data[fld])
        else:
            data[fld] = 0.0
    data["hard_limit"] = bool(int(data.get("hard_limit") or 0))
    return data


def upsert_tier(tier: dict) -> dict:
    r = get_redis()
    name = tier["name"]
    key = f"api:tier:{name}"
    mapping = {
        "name": name,
        "rps": int(tier.get("rps") or 0),
        "rpm": int(tier.get("rpm") or 0),
        "monthly_quota": int(tier.get("monthly_quota") or 0),
        "overage_price": float(tier.get("overage_price") or 0.0),
        "currency": tier.get("currency") or "USD",
        "hard_limit": 1 if bool(tier.get("hard_limit")) else 0,
    }
    r.hset(key, mapping=mapping)
    return get_tier(name)


def list_tiers() -> list[dict]:
    r = get_redis()
    tiers = []
    for key in r.scan_iter(match="api:tier:*", count=100):
        name = key.split(":")[-1]
        t = get_tier(name)
        if t:
            tiers.append(t)
    return tiers

