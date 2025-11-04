def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def pct(v, p):
    return v * (1 + p)


def safe_get(d, path, default=None):
    cur = d
    try:
        for key in path:
            if cur is None:
                return default
            cur = cur.get(key)
        if cur is None:
            return default
        return cur
    except Exception:
        return default


def sum_costs(quantity_map, unit_costs):
    total = 0.0
    for k, qty in (quantity_map or {}).items():
        cost_key = _normalize_cost_key(k)
        if cost_key in unit_costs:
            total += float(qty) * float(unit_costs[cost_key])
    return total


def _normalize_cost_key(k):
    # Align input metric keys to our cost keys.
    mapping = {
        "api_calls": "api_call",
        "api_call": "api_call",
        "tokens": "ai_token",
        "ai_tokens": "ai_token",
        "gpu": "gpu_minute",
        "gpu_minutes": "gpu_minute",
        "storage": "storage_gb_month",
        "storage_gb": "storage_gb_month",
        "bandwidth": "bandwidth_gb",
        "egress_gb": "bandwidth_gb",
    }
    return mapping.get(k, k)


def merge_costs(base_costs, overrides):
    merged = dict(base_costs or {})
    for k, v in (overrides or {}).items():
        merged[k] = v
    return merged

