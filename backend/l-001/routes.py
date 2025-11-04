from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError

from database import db
from models import Team, Project, ModelDef, LedgerEntry
from services import create_ledger_entry, parse_iso_datetime, ledger_query, team_summary, project_summary, model_stats

api_bp = Blueprint("api", __name__)


def bad_request(message, status=400):
    return jsonify({"error": message}), status


@api_bp.post("/teams")
def create_team():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return bad_request("name is required")
    t = Team(name=name)
    db.session.add(t)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return bad_request("team with this name already exists")
    return jsonify(t.to_dict()), 201


@api_bp.get("/teams")
def list_teams():
    teams = Team.query.order_by(Team.name.asc()).all()
    return jsonify([t.to_dict() for t in teams])


@api_bp.get("/teams/<int:team_id>/summary")
def get_team_summary(team_id: int):
    team = db.session.get(Team, team_id)
    if not team:
        return bad_request("team not found", status=404)
    start = parse_iso_datetime(request.args.get("start"))
    end = parse_iso_datetime(request.args.get("end"))
    summary = team_summary(team_id, start=start, end=end)
    return jsonify({"team": team.to_dict(), **summary})


@api_bp.post("/projects")
def create_project():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    team_id = data.get("team_id")
    if not name or not team_id:
        return bad_request("name and team_id are required")
    if not db.session.get(Team, team_id):
        return bad_request("team not found")
    p = Project(name=name, team_id=team_id)
    db.session.add(p)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return bad_request("project with this name already exists for the team")
    return jsonify(p.to_dict()), 201


@api_bp.get("/projects")
def list_projects():
    projects = Project.query.order_by(Project.id.desc()).all()
    return jsonify([p.to_dict() for p in projects])


@api_bp.get("/projects/<int:project_id>/summary")
def get_project_summary(project_id: int):
    project = db.session.get(Project, project_id)
    if not project:
        return bad_request("project not found", status=404)
    start = parse_iso_datetime(request.args.get("start"))
    end = parse_iso_datetime(request.args.get("end"))
    summary = project_summary(project_id, start=start, end=end)
    return jsonify({"project": project.to_dict(), **summary})


@api_bp.post("/models")
def create_model():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    provider = (data.get("provider") or None)
    input_cost_per_1k = data.get("input_cost_per_1k")
    output_cost_per_1k = data.get("output_cost_per_1k")
    currency = (data.get("currency") or "USD").strip().upper()

    if not name or input_cost_per_1k is None or output_cost_per_1k is None:
        return bad_request("name, input_cost_per_1k and output_cost_per_1k are required")

    try:
        model = ModelDef(
            name=name,
            provider=provider,
            input_cost_per_1k=input_cost_per_1k,
            output_cost_per_1k=output_cost_per_1k,
            currency=currency,
        )
        db.session.add(model)
        db.session.commit()
        return jsonify(model.to_dict()), 201
    except IntegrityError:
        db.session.rollback()
        return bad_request("model with this name already exists")


@api_bp.get("/models")
def list_models():
    models = ModelDef.query.order_by(ModelDef.name.asc()).all()
    return jsonify([m.to_dict() for m in models])


@api_bp.post("/usage")
def add_usage():
    data = request.get_json(silent=True) or {}
    required = ["project_id", "model_id"]
    for key in required:
        if key not in data:
            return bad_request(f"{key} is required")

    # Optional values
    team_id = data.get("team_id")
    input_tokens = int(data.get("input_tokens") or 0)
    output_tokens = int(data.get("output_tokens") or 0)
    ts = parse_iso_datetime(data.get("ts"))
    try:
        entry = create_ledger_entry(
            project_id=int(data["project_id"]),
            model_id=int(data["model_id"]),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            ts=ts,
            team_id=int(team_id) if team_id is not None else None,
            user=data.get("user"),
            note=data.get("note"),
            metadata=data.get("metadata"),
            tags=data.get("tags"),
        )
        return jsonify(entry.to_dict()), 201
    except ValueError as ve:
        return bad_request(str(ve))


@api_bp.get("/ledger")
def list_ledger():
    args = request.args
    team_id = args.get("team_id", type=int)
    project_id = args.get("project_id", type=int)
    model_id = args.get("model_id", type=int)

    start = parse_iso_datetime(args.get("start"))
    end = parse_iso_datetime(args.get("end"))

    q = ledger_query(team_id=team_id, project_id=project_id, model_id=model_id, start=start, end=end)
    q = q.order_by(LedgerEntry.ts.desc(), LedgerEntry.id.desc())

    limit = args.get("limit", default=100, type=int)
    offset = args.get("offset", default=0, type=int)

    total = q.count()
    rows = q.offset(offset).limit(min(limit, 1000)).all()

    data = [r.to_dict() for r in rows]
    # Enrich with names
    project_ids = {r.project_id for r in rows}
    model_ids = {r.model_id for r in rows}
    team_ids = {r.team_id for r in rows}

    projects = {p.id: p for p in Project.query.filter(Project.id.in_(project_ids)).all()} if project_ids else {}
    models = {m.id: m for m in ModelDef.query.filter(ModelDef.id.in_(model_ids)).all()} if model_ids else {}
    teams = {t.id: t for t in Team.query.filter(Team.id.in_(team_ids)).all()} if team_ids else {}

    for item in data:
        pid = item["project_id"]
        mid = item["model_id"]
        tid = item["team_id"]
        item["project_name"] = projects.get(pid).name if pid in projects else None
        item["model_name"] = models.get(mid).name if mid in models else None
        item["provider"] = models.get(mid).provider if mid in models else None
        item["team_name"] = teams.get(tid).name if tid in teams else None

    return jsonify({
        "total": total,
        "count": len(data),
        "offset": offset,
        "limit": limit,
        "items": data,
    })


@api_bp.get("/stats/models")
def stats_models():
    args = request.args
    team_id = args.get("team_id", type=int)
    project_id = args.get("project_id", type=int)
    start = parse_iso_datetime(args.get("start"))
    end = parse_iso_datetime(args.get("end"))

    data = model_stats(team_id=team_id, project_id=project_id, start=start, end=end)
    return jsonify({"items": data})

