from flask import Blueprint, request
from datetime import datetime, timedelta
from dateutil import parser as dateparser
from sqlalchemy import and_

from models import db, Agent, SLA, MetricEvent
from config import Config
from metrics import compute_agent_metrics, compute_sla_report, get_agent_sla

api_bp = Blueprint("api", __name__)


def _parse_time_range(req):
    now = datetime.utcnow()
    default_start = now - timedelta(days=Config.DEFAULT_WINDOW_DAYS)
    start_s = req.args.get("from") or req.args.get("start")
    end_s = req.args.get("to") or req.args.get("end")
    try:
        start = dateparser.isoparse(start_s) if start_s else default_start
    except Exception:
        start = default_start
    try:
        end = dateparser.isoparse(end_s) if end_s else now
    except Exception:
        end = now
    if end < start:
        start, end = end, start
    return start, end


@api_bp.post("/agents")
def create_agent():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    if not name:
        return {"ok": False, "error": "name is required"}, 400

    agent = Agent(
        name=name,
        description=data.get("description"),
        metadata=data.get("metadata"),
    )
    db.session.add(agent)
    db.session.flush()

    sla_data = data.get("sla")
    if sla_data:
        sla = SLA(
            agent_id=agent.id,
            target_uptime=sla_data.get("target_uptime", Config.DEFAULT_SLA["target_uptime"]),
            max_error_rate=sla_data.get("max_error_rate", Config.DEFAULT_SLA["max_error_rate"]),
            p95_latency_ms_target=sla_data.get("p95_latency_ms_target", Config.DEFAULT_SLA["p95_latency_ms_target"]),
            min_success_rate=sla_data.get("min_success_rate", Config.DEFAULT_SLA["min_success_rate"]),
            max_cost_per_interaction_usd=sla_data.get("max_cost_per_interaction_usd", Config.DEFAULT_SLA.get("max_cost_per_interaction_usd")),
        )
        db.session.add(sla)

    db.session.commit()

    return {"ok": True, "data": {"id": agent.id, "name": agent.name, "description": agent.description, "metadata": agent.metadata, "sla": get_agent_sla(agent)}}, 201


@api_bp.get("/agents")
def list_agents():
    agents = Agent.query.order_by(Agent.created_at.desc()).all()
    return {
        "ok": True,
        "data": [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "metadata": a.metadata,
                "created_at": a.created_at.isoformat(),
                "updated_at": a.updated_at.isoformat(),
                "sla": get_agent_sla(a),
            }
            for a in agents
        ],
    }


@api_bp.get("/agents/<agent_id>")
def get_agent(agent_id):
    agent = Agent.query.get(agent_id)
    if not agent:
        return {"ok": False, "error": "agent not found"}, 404
    return {
        "ok": True,
        "data": {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "metadata": agent.metadata,
            "created_at": agent.created_at.isoformat(),
            "updated_at": agent.updated_at.isoformat(),
            "sla": get_agent_sla(agent),
        },
    }


@api_bp.patch("/agents/<agent_id>")
def update_agent(agent_id):
    agent = Agent.query.get(agent_id)
    if not agent:
        return {"ok": False, "error": "agent not found"}, 404

    data = request.get_json(force=True, silent=True) or {}
    if "name" in data and data["name"]:
        agent.name = data["name"]
    if "description" in data:
        agent.description = data["description"]
    if "metadata" in data:
        agent.metadata = data["metadata"]

    db.session.commit()
    return {"ok": True, "data": {"id": agent.id, "name": agent.name, "description": agent.description, "metadata": agent.metadata}}


@api_bp.put("/agents/<agent_id>/sla")
def upsert_sla(agent_id):
    agent = Agent.query.get(agent_id)
    if not agent:
        return {"ok": False, "error": "agent not found"}, 404

    data = request.get_json(force=True, silent=True) or {}
    existing = agent.sla
    if not existing:
        existing = SLA(agent_id=agent.id,
                       target_uptime=Config.DEFAULT_SLA["target_uptime"],
                       max_error_rate=Config.DEFAULT_SLA["max_error_rate"],
                       p95_latency_ms_target=Config.DEFAULT_SLA["p95_latency_ms_target"],
                       min_success_rate=Config.DEFAULT_SLA["min_success_rate"],
                       max_cost_per_interaction_usd=Config.DEFAULT_SLA.get("max_cost_per_interaction_usd"))
        db.session.add(existing)

    for k in ["target_uptime", "max_error_rate", "p95_latency_ms_target", "min_success_rate", "max_cost_per_interaction_usd"]:
        if k in data and data[k] is not None:
            setattr(existing, k, data[k])

    db.session.commit()

    return {"ok": True, "data": {
        "agent_id": agent.id,
        "sla": {
            "target_uptime": existing.target_uptime,
            "max_error_rate": existing.max_error_rate,
            "p95_latency_ms_target": existing.p95_latency_ms_target,
            "min_success_rate": existing.min_success_rate,
            "max_cost_per_interaction_usd": existing.max_cost_per_interaction_usd,
        }
    }}


@api_bp.get("/agents/<agent_id>/sla")
def get_sla(agent_id):
    agent = Agent.query.get(agent_id)
    if not agent:
        return {"ok": False, "error": "agent not found"}, 404
    return {"ok": True, "data": {"agent_id": agent.id, "sla": get_agent_sla(agent)}}


@api_bp.post("/events")
def ingest_events():
    payload = request.get_json(force=True, silent=True) or {}

    if isinstance(payload, dict) and "events" in payload and isinstance(payload["events"], list):
        events = payload["events"]
    else:
        # Single event
        events = [payload]

    created = []
    errors = []

    for idx, e in enumerate(events):
        agent_id = e.get("agent_id")
        if not agent_id or not Agent.query.get(agent_id):
            errors.append({"index": idx, "error": "invalid agent_id"})
            continue

        etype = e.get("type", "interaction")
        if etype not in ("interaction", "error", "downtime", "custom"):
            errors.append({"index": idx, "error": "invalid type"})
            continue

        ts_raw = e.get("ts")
        try:
            ts = dateparser.isoparse(ts_raw) if ts_raw else datetime.utcnow()
        except Exception:
            ts = datetime.utcnow()

        me = MetricEvent(
            agent_id=agent_id,
            ts=ts,
            type=etype,
            duration_ms=e.get("duration_ms"),
            success=e.get("success"),
            error_code=e.get("error_code"),
            input_tokens=e.get("input_tokens"),
            output_tokens=e.get("output_tokens"),
            cost_usd=e.get("cost_usd"),
            revenue_usd=e.get("revenue_usd"),
            metadata=e.get("metadata"),
        )
        db.session.add(me)
        created.append(me)

    db.session.commit()

    return {
        "ok": len(errors) == 0,
        "created": len(created),
        "errors": errors,
        "ids": [e.id for e in created],
    }, (200 if len(errors) == 0 else 207)


@api_bp.get("/events")
def list_events():
    start, end = _parse_time_range(request)
    agent_id = request.args.get("agent_id")
    etype = request.args.get("type")

    q = MetricEvent.query.filter(MetricEvent.ts >= start, MetricEvent.ts <= end)
    if agent_id:
        q = q.filter(MetricEvent.agent_id == agent_id)
    if etype:
        q = q.filter(MetricEvent.type == etype)

    q = q.order_by(MetricEvent.ts.desc()).limit(1000)

    events = q.all()
    return {
        "ok": True,
        "data": [
            {
                "id": e.id,
                "agent_id": e.agent_id,
                "ts": e.ts.isoformat(),
                "type": e.type,
                "duration_ms": e.duration_ms,
                "success": e.success,
                "error_code": e.error_code,
                "input_tokens": e.input_tokens,
                "output_tokens": e.output_tokens,
                "cost_usd": e.cost_usd,
                "revenue_usd": e.revenue_usd,
                "metadata": e.metadata,
            }
            for e in events
        ],
        "window": {"start": start.isoformat(), "end": end.isoformat()},
    }


@api_bp.get("/metrics/agents/<agent_id>/summary")
def agent_summary(agent_id):
    agent = Agent.query.get(agent_id)
    if not agent:
        return {"ok": False, "error": "agent not found"}, 404

    start, end = _parse_time_range(request)
    summary = compute_agent_metrics(agent_id, start, end)
    return {"ok": True, "data": summary}


@api_bp.get("/metrics/agents/<agent_id>/sla_report")
def agent_sla_report(agent_id):
    agent = Agent.query.get(agent_id)
    if not agent:
        return {"ok": False, "error": "agent not found"}, 404

    start, end = _parse_time_range(request)
    report = compute_sla_report(agent_id, start, end)
    return {"ok": True, "data": report}


@api_bp.get("/metrics/agents")
def all_agents_summary():
    start, end = _parse_time_range(request)
    agents = Agent.query.all()
    data = [compute_agent_metrics(a.id, start, end) for a in agents]
    return {"ok": True, "data": data, "window": {"start": start.isoformat(), "end": end.isoformat()}}

