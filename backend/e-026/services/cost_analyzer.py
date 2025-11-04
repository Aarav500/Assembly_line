from typing import Dict, Optional
from services.cost_models import price_for, recommend_type

HOURS_PER_MONTH = 730


def _metric(resource: Dict, key: str, default: float = 0.0) -> float:
    return float(((resource or {}).get("metrics") or {}).get(key, default))


def _util(resource: Dict):
    avg_cpu = _metric(resource, "avg_cpu", 0.0)  # 0..1
    peak_cpu = _metric(resource, "peak_cpu", 0.0)
    avg_mem = _metric(resource, "avg_mem", 0.0)
    peak_mem = _metric(resource, "peak_mem", 0.0)
    idle_h = _metric(resource, "idle_hours_7d", 0.0)
    return avg_cpu, peak_cpu, avg_mem, peak_mem, idle_h


def analyze_resource(resource: Dict) -> Optional[Dict]:
    if not resource:
        return None

    instance_type = resource.get("instance_type") or "standard.large"
    region = resource.get("region")
    cost_per_hour = resource.get("cost_per_hour") or price_for(instance_type, region)

    avg_cpu, peak_cpu, avg_mem, peak_mem, idle_h = _util(resource)

    # Terminate suggestion for idle resources
    if idle_h >= 140 and avg_cpu < 0.03 and avg_mem < 0.10:
        monthly_cost = cost_per_hour * HOURS_PER_MONTH
        suggestion = {
            "resource_id": resource.get("id"),
            "resource_name": resource.get("name"),
            "provider": resource.get("provider"),
            "region": region,
            "action": "terminate",
            "recommended_type": None,
            "estimated_monthly_savings": round(monthly_cost, 2),
            "confidence": 0.85,
            "rationale": "Resource is idle for most of the week and consumes negligible CPU/memory.",
            "resource": resource,
            "metrics": {
                "avg_cpu": avg_cpu,
                "peak_cpu": peak_cpu,
                "avg_mem": avg_mem,
                "peak_mem": peak_mem,
                "idle_hours_7d": idle_h,
            },
        }
        return suggestion

    # Downsize
    if avg_cpu < 0.15 and avg_mem < 0.30 and peak_cpu < 0.40 and peak_mem < 0.50:
        steps = 2 if (avg_cpu < 0.08 and avg_mem < 0.15 and peak_cpu < 0.25) else 1
        target_type = recommend_type(instance_type, direction="down", aggressiveness=steps)
        if target_type:
            target_price = price_for(target_type, region)
            savings = max(0.0, (cost_per_hour - target_price) * HOURS_PER_MONTH)
            return {
                "resource_id": resource.get("id"),
                "resource_name": resource.get("name"),
                "provider": resource.get("provider"),
                "region": region,
                "action": "downsize",
                "recommended_type": target_type,
                "estimated_monthly_savings": round(savings, 2),
                "confidence": 0.8 if steps == 1 else 0.7,
                "rationale": "Consistently low CPU/memory utilization. Downsize to reduce cost.",
                "resource": resource,
                "metrics": {
                    "avg_cpu": avg_cpu,
                    "peak_cpu": peak_cpu,
                    "avg_mem": avg_mem,
                    "peak_mem": peak_mem,
                    "idle_hours_7d": idle_h,
                },
            }

    # Upsize
    if avg_cpu > 0.85 or peak_cpu > 0.95 or avg_mem > 0.85 or peak_mem > 0.95:
        steps = 2 if (avg_cpu > 0.92 or avg_mem > 0.92 or peak_cpu > 0.98 or peak_mem > 0.98) else 1
        target_type = recommend_type(instance_type, direction="up", aggressiveness=steps)
        if target_type:
            target_price = price_for(target_type, region)
            extra_cost = max(0.0, (target_price - cost_per_hour) * HOURS_PER_MONTH)
            return {
                "resource_id": resource.get("id"),
                "resource_name": resource.get("name"),
                "provider": resource.get("provider"),
                "region": region,
                "action": "upsize",
                "recommended_type": target_type,
                "estimated_monthly_savings": round(-extra_cost, 2),  # negative means additional cost
                "confidence": 0.75 if steps == 1 else 0.7,
                "rationale": "High CPU/memory utilization indicates risk of saturation. Consider upsizing.",
                "resource": resource,
                "metrics": {
                    "avg_cpu": avg_cpu,
                    "peak_cpu": peak_cpu,
                    "avg_mem": avg_mem,
                    "peak_mem": peak_mem,
                    "idle_hours_7d": idle_h,
                },
            }

    # No change recommended
    return {
        "resource_id": resource.get("id"),
        "resource_name": resource.get("name"),
        "provider": resource.get("provider"),
        "region": resource.get("region"),
        "action": "rightsizing_not_needed",
        "recommended_type": None,
        "estimated_monthly_savings": 0.0,
        "confidence": 0.65,
        "rationale": "Resource utilization within target thresholds.",
        "resource": resource,
        "metrics": {
            "avg_cpu": avg_cpu,
            "peak_cpu": peak_cpu,
            "avg_mem": avg_mem,
            "peak_mem": peak_mem,
            "idle_hours_7d": idle_h,
        },
    }

