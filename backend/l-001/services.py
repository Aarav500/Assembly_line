from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

from sqlalchemy import func, and_

from database import db
from models import Team, Project, ModelDef, LedgerEntry


DECIMAL_CTX = Decimal("0.00000001")


def to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(0)


def compute_cost(model: ModelDef, input_tokens: int, output_tokens: int) -> Tuple[Decimal, Decimal, Decimal]:
    in_cost = (to_decimal(input_tokens) * to_decimal(model.input_cost_per_1k) / Decimal(1000)).quantize(DECIMAL_CTX, rounding=ROUND_HALF_UP)
    out_cost = (to_decimal(output_tokens) * to_decimal(model.output_cost_per_1k) / Decimal(1000)).quantize(DECIMAL_CTX, rounding=ROUND_HALF_UP)
    total_cost = (in_cost + out_cost).quantize(DECIMAL_CTX, rounding=ROUND_HALF_UP)
    return in_cost, out_cost, total_cost


def ensure_project_belongs_to_team(project: Project, team_id: Optional[int]):
    if team_id is not None and project.team_id != team_id:
        raise ValueError("Project does not belong to the specified team")


def create_ledger_entry(*, project_id: int, model_id: int, input_tokens: int = 0, output_tokens: int = 0,
                        ts: Optional[datetime] = None, team_id: Optional[int] = None, user: Optional[str] = None,
                        note: Optional[str] = None, metadata: Optional[dict] = None, tags: Optional[list] = None) -> LedgerEntry:
    project = db.session.get(Project, project_id)
    if not project:
        raise ValueError("Project not found")

    ensure_project_belongs_to_team(project, team_id)

    team = db.session.get(Team, project.team_id)
    model = db.session.get(ModelDef, model_id)
    if not model:
        raise ValueError("Model not found")

    in_cost, out_cost, total_cost = compute_cost(model, int(input_tokens or 0), int(output_tokens or 0))

    entry = LedgerEntry(
        ts=ts or datetime.utcnow(),
        team_id=team.id,
        project_id=project.id,
        model_id=model.id,
        input_tokens=int(input_tokens or 0),
        output_tokens=int(output_tokens or 0),
        total_tokens=int(input_tokens or 0) + int(output_tokens or 0),
        input_cost=in_cost,
        output_cost=out_cost,
        total_cost=total_cost,
        currency=model.currency,
        user=user,
        note=note,
        metadata=metadata or None,
        tags=",".join(tags) if tags else None,
    )

    db.session.add(entry)
    db.session.commit()
    return entry


def parse_iso_datetime(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # Allow trailing Z
        if s.endswith("Z"):
            s = s[:-1]
        return datetime.fromisoformat(s)
    except Exception:
        return None


def ledger_query(team_id: Optional[int] = None, project_id: Optional[int] = None,
                 model_id: Optional[int] = None, start: Optional[datetime] = None,
                 end: Optional[datetime] = None):
    q = db.session.query(LedgerEntry)
    conditions = []
    if team_id:
        conditions.append(LedgerEntry.team_id == team_id)
    if project_id:
        conditions.append(LedgerEntry.project_id == project_id)
    if model_id:
        conditions.append(LedgerEntry.model_id == model_id)
    if start:
        conditions.append(LedgerEntry.ts >= start)
    if end:
        conditions.append(LedgerEntry.ts <= end)
    if conditions:
        q = q.filter(and_(*conditions))
    return q


def aggregate_totals(q):
    sums = q.with_entities(
        func.coalesce(func.sum(LedgerEntry.input_tokens), 0),
        func.coalesce(func.sum(LedgerEntry.output_tokens), 0),
        func.coalesce(func.sum(LedgerEntry.total_tokens), 0),
        func.coalesce(func.sum(LedgerEntry.input_cost), 0),
        func.coalesce(func.sum(LedgerEntry.output_cost), 0),
        func.coalesce(func.sum(LedgerEntry.total_cost), 0),
    ).first()
    input_tokens, output_tokens, total_tokens, input_cost, output_cost, total_cost = sums
    return {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "total_tokens": int(total_tokens or 0),
        "input_cost": float(input_cost or 0),
        "output_cost": float(output_cost or 0),
        "total_cost": float(total_cost or 0),
    }


def team_summary(team_id: int, start: Optional[datetime] = None, end: Optional[datetime] = None):
    base_q = ledger_query(team_id=team_id, start=start, end=end)
    totals = aggregate_totals(base_q)

    # Per project
    per_project_rows = db.session.query(
        LedgerEntry.project_id,
        func.coalesce(func.sum(LedgerEntry.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(LedgerEntry.total_cost), 0).label("total_cost"),
    ).filter(LedgerEntry.team_id == team_id)
    if start:
        per_project_rows = per_project_rows.filter(LedgerEntry.ts >= start)
    if end:
        per_project_rows = per_project_rows.filter(LedgerEntry.ts <= end)
    per_project_rows = per_project_rows.group_by(LedgerEntry.project_id).all()

    projects = []
    for pid, p_tokens, p_cost in per_project_rows:
        project = db.session.get(Project, pid)
        projects.append({
            "project_id": pid,
            "project_name": project.name if project else str(pid),
            "total_tokens": int(p_tokens or 0),
            "total_cost": float(p_cost or 0),
        })

    # Per model across team
    per_model_rows = db.session.query(
        LedgerEntry.model_id,
        func.coalesce(func.sum(LedgerEntry.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(LedgerEntry.total_cost), 0).label("total_cost"),
    ).filter(LedgerEntry.team_id == team_id)
    if start:
        per_model_rows = per_model_rows.filter(LedgerEntry.ts >= start)
    if end:
        per_model_rows = per_model_rows.filter(LedgerEntry.ts <= end)
    per_model_rows = per_model_rows.group_by(LedgerEntry.model_id).all()

    models = []
    for mid, m_tokens, m_cost in per_model_rows:
        model = db.session.get(ModelDef, mid)
        models.append({
            "model_id": mid,
            "model_name": model.name if model else str(mid),
            "provider": model.provider if model else None,
            "total_tokens": int(m_tokens or 0),
            "total_cost": float(m_cost or 0),
        })

    return {"totals": totals, "projects": projects, "models": models}


def project_summary(project_id: int, start: Optional[datetime] = None, end: Optional[datetime] = None):
    base_q = ledger_query(project_id=project_id, start=start, end=end)
    totals = aggregate_totals(base_q)

    # Per model for the project
    per_model_rows = db.session.query(
        LedgerEntry.model_id,
        func.coalesce(func.sum(LedgerEntry.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(LedgerEntry.total_cost), 0).label("total_cost"),
    ).filter(LedgerEntry.project_id == project_id)
    if start:
        per_model_rows = per_model_rows.filter(LedgerEntry.ts >= start)
    if end:
        per_model_rows = per_model_rows.filter(LedgerEntry.ts <= end)
    per_model_rows = per_model_rows.group_by(LedgerEntry.model_id).all()

    models = []
    for mid, m_tokens, m_cost in per_model_rows:
        model = db.session.get(ModelDef, mid)
        models.append({
            "model_id": mid,
            "model_name": model.name if model else str(mid),
            "provider": model.provider if model else None,
            "total_tokens": int(m_tokens or 0),
            "total_cost": float(m_cost or 0),
        })

    return {"totals": totals, "models": models}


def model_stats(team_id: Optional[int] = None, project_id: Optional[int] = None,
                start: Optional[datetime] = None, end: Optional[datetime] = None):
    q = db.session.query(
        LedgerEntry.model_id,
        func.coalesce(func.sum(LedgerEntry.input_tokens), 0),
        func.coalesce(func.sum(LedgerEntry.output_tokens), 0),
        func.coalesce(func.sum(LedgerEntry.total_tokens), 0),
        func.coalesce(func.sum(LedgerEntry.input_cost), 0),
        func.coalesce(func.sum(LedgerEntry.output_cost), 0),
        func.coalesce(func.sum(LedgerEntry.total_cost), 0),
    )
    if team_id:
        q = q.filter(LedgerEntry.team_id == team_id)
    if project_id:
        q = q.filter(LedgerEntry.project_id == project_id)
    if start:
        q = q.filter(LedgerEntry.ts >= start)
    if end:
        q = q.filter(LedgerEntry.ts <= end)
    q = q.group_by(LedgerEntry.model_id)

    rows = q.all()

    out = []
    for mid, in_t, out_t, tot_t, in_c, out_c, tot_c in rows:
        model = db.session.get(ModelDef, mid)
        out.append({
            "model_id": mid,
            "model_name": model.name if model else str(mid),
            "provider": model.provider if model else None,
            "input_tokens": int(in_t or 0),
            "output_tokens": int(out_t or 0),
            "total_tokens": int(tot_t or 0),
            "input_cost": float(in_c or 0),
            "output_cost": float(out_c or 0),
            "total_cost": float(tot_c or 0),
        })
    return out

