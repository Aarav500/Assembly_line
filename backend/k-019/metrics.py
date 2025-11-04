import math
from datetime import datetime, timedelta
from sqlalchemy import and_
from models import db, Agent, MetricEvent, SLA
from config import Config


def _percentile(sorted_values, p):
    if not sorted_values:
        return None
    if p <= 0:
        return sorted_values[0]
    if p >= 100:
        return sorted_values[-1]
    k = (p / 100.0) * (len(sorted_values) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)
    return d0 + d1


def compute_agent_metrics(agent_id, start, end):
    q = db.session.query(MetricEvent).filter(
        and_(
            MetricEvent.agent_id == agent_id,
            MetricEvent.ts >= start,
            MetricEvent.ts <= end,
        )
    )
    events = q.all()

    total_window_ms = max(1, int((end - start).total_seconds() * 1000))

    interaction_events = [e for e in events if e.type == "interaction"]
    error_events = [e for e in events if e.type == "error"]
    downtime_events = [e for e in events if e.type == "downtime"]

    total_interactions = len(interaction_events)
    successes = sum(1 for e in interaction_events if e.success is True)
    interaction_failures = sum(1 for e in interaction_events if e.success is False)
    errors = len(error_events) + interaction_failures

    durations = [e.duration_ms for e in interaction_events if isinstance(e.duration_ms, (int, float))]
    durations_sorted = sorted(durations)

    avg_latency_ms = (sum(durations) / len(durations)) if durations else None
    p95_latency_ms = _percentile(durations_sorted, 95) if durations_sorted else None

    downtime_ms = sum(e.duration_ms or 0 for e in downtime_events)
    uptime_percent = max(0.0, 1.0 - (float(downtime_ms) / float(total_window_ms))) * 100.0

    total_cost_usd = sum(e.cost_usd or 0.0 for e in events)
    total_revenue_usd = sum(e.revenue_usd or 0.0 for e in events)

    cost_per_interaction = (total_cost_usd / total_interactions) if total_interactions > 0 else None
    success_rate = (successes / total_interactions) if total_interactions > 0 else None
    error_rate = (errors / total_interactions) if total_interactions > 0 else None

    roi_abs = (total_revenue_usd - total_cost_usd)
    roi_ratio = ((roi_abs / total_cost_usd) if total_cost_usd > 0 else None)
    gross_margin = (((total_revenue_usd - total_cost_usd) / total_revenue_usd) if total_revenue_usd > 0 else None)

    failure_count = len(error_events) + interaction_failures
    mttr_seconds = ((downtime_ms / 1000.0) / failure_count) if failure_count > 0 else None
    total_uptime_ms = max(0, total_window_ms - downtime_ms)
    mtbf_seconds = ((total_uptime_ms / 1000.0) / failure_count) if failure_count > 0 else None

    return {
        "agent_id": agent_id,
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "duration_ms": total_window_ms,
        },
        "traffic": {
            "total_interactions": total_interactions,
            "successes": successes,
            "errors": errors,
            "success_rate": success_rate,
            "error_rate": error_rate,
        },
        "latency": {
            "avg_ms": avg_latency_ms,
            "p95_ms": p95_latency_ms,
        },
        "reliability": {
            "downtime_ms": downtime_ms,
            "uptime_percent": uptime_percent,
            "mttr_seconds": mttr_seconds,
            "mtbf_seconds": mtbf_seconds,
        },
        "economics": {
            "cost_usd": total_cost_usd,
            "revenue_usd": total_revenue_usd,
            "cost_per_interaction_usd": cost_per_interaction,
            "roi_abs_usd": roi_abs,
            "roi_ratio": roi_ratio,
            "gross_margin": gross_margin,
        },
    }


def get_agent_sla(agent):
    defaults = Config.DEFAULT_SLA
    if agent.sla:
        return {
            "target_uptime": agent.sla.target_uptime,
            "max_error_rate": agent.sla.max_error_rate,
            "p95_latency_ms_target": agent.sla.p95_latency_ms_target,
            "min_success_rate": agent.sla.min_success_rate,
            "max_cost_per_interaction_usd": agent.sla.max_cost_per_interaction_usd,
        }
    return defaults


def compute_sla_report(agent_id, start, end):
    agent = Agent.query.get(agent_id)
    if not agent:
        return None
    m = compute_agent_metrics(agent_id, start, end)
    sla = get_agent_sla(agent)

    sla_checks = {}

    # Uptime
    uptime_ok = (m["reliability"]["uptime_percent"] is not None) and (m["reliability"]["uptime_percent"] >= sla["target_uptime"] * 100.0)
    sla_checks["uptime"] = {
        "target_percent": sla["target_uptime"] * 100.0,
        "actual_percent": m["reliability"]["uptime_percent"],
        "ok": bool(uptime_ok),
    }

    # Error rate
    err_rate = m["traffic"]["error_rate"] if m["traffic"]["error_rate"] is not None else None
    err_ok = (err_rate is not None) and (err_rate <= sla["max_error_rate"])
    sla_checks["error_rate"] = {
        "target_fraction": sla["max_error_rate"],
        "actual_fraction": err_rate,
        "ok": bool(err_ok),
    }

    # Success rate
    succ_rate = m["traffic"]["success_rate"] if m["traffic"]["success_rate"] is not None else None
    succ_ok = (succ_rate is not None) and (succ_rate >= sla["min_success_rate"])
    sla_checks["success_rate"] = {
        "target_fraction": sla["min_success_rate"],
        "actual_fraction": succ_rate,
        "ok": bool(succ_ok),
    }

    # P95 Latency
    p95 = m["latency"]["p95_ms"]
    p95_ok = (p95 is not None) and (p95 <= sla["p95_latency_ms_target"])
    sla_checks["p95_latency_ms"] = {
        "target_ms": sla["p95_latency_ms_target"],
        "actual_ms": p95,
        "ok": bool(p95_ok),
    }

    # Cost per interaction (optional)
    cpi_target = sla.get("max_cost_per_interaction_usd")
    cpi_actual = m["economics"]["cost_per_interaction_usd"]
    if cpi_target is not None:
        cpi_ok = (cpi_actual is not None) and (cpi_actual <= cpi_target)
    else:
        cpi_ok = True
    sla_checks["cost_per_interaction_usd"] = {
        "target_usd": cpi_target,
        "actual_usd": cpi_actual,
        "ok": bool(cpi_ok),
    }

    all_ok = all(v.get("ok", False) for v in sla_checks.values())

    return {
        "agent_id": agent_id,
        "window": m["window"],
        "sla": sla,
        "metrics": m,
        "checks": sla_checks,
        "ok": bool(all_ok),
    }

