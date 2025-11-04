from datetime import datetime
from flask import Blueprint, jsonify, request, render_template, redirect, url_for, abort
from sqlalchemy.exc import IntegrityError
from models import db, Idea, Risk, Mitigation

bp = Blueprint("main", __name__)

# -------- UI Routes --------
@bp.route("/")
def home():
    return redirect(url_for("main.list_ideas"))

@bp.route("/ideas", methods=["GET", "POST"])
def list_ideas():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description")
        if not title:
            return render_template("index.html", ideas=Idea.query.order_by(Idea.created_at.desc()).all(), error="Title is required")
        idea = Idea(title=title, description=description)
        db.session.add(idea)
        db.session.commit()
        return redirect(url_for("main.view_idea", idea_id=idea.id))
    ideas = Idea.query.order_by(Idea.created_at.desc()).all()
    return render_template("index.html", ideas=ideas)

@bp.route("/ideas/<int:idea_id>", methods=["GET"]) 
def view_idea(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    risks = Risk.query.filter_by(idea_id=idea.id).order_by(Risk.created_at.desc()).all()
    return render_template("idea_detail.html", idea=idea, risks=risks)

@bp.route("/ideas/<int:idea_id>/risks", methods=["POST"]) 
def create_risk_for_idea(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    title = request.form.get("title", "").strip()
    description = request.form.get("description")
    owner = request.form.get("owner")
    severity = int(request.form.get("severity", 3))
    likelihood = int(request.form.get("likelihood", 3))
    severity = min(5, max(1, severity))
    likelihood = min(5, max(1, likelihood))
    if not title:
        return redirect(url_for("main.view_idea", idea_id=idea.id))
    risk = Risk(idea_id=idea.id, title=title, description=description, owner=owner, severity=severity, likelihood=likelihood)
    db.session.add(risk)
    db.session.commit()
    return redirect(url_for("main.view_risk", risk_id=risk.id))

@bp.route("/risks/<int:risk_id>", methods=["GET"]) 
def view_risk(risk_id):
    risk = Risk.query.get_or_404(risk_id)
    return render_template("risk_detail.html", risk=risk)

@bp.route("/risks/<int:risk_id>/transition", methods=["POST"]) 
def transition_risk_ui(risk_id):
    risk = Risk.query.get_or_404(risk_id)
    to_state = request.form.get("to_state")
    actor = request.form.get("actor") or "user"
    note = request.form.get("note")
    try:
        risk.transition(to_state, actor=actor, note=note)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return render_template("risk_detail.html", risk=risk, error=str(e)), 400
    return redirect(url_for("main.view_risk", risk_id=risk.id))

@bp.route("/risks/<int:risk_id>/mitigations", methods=["POST"]) 
def add_mitigation_ui(risk_id):
    risk = Risk.query.get_or_404(risk_id)
    title = request.form.get("title", "").strip()
    description = request.form.get("description")
    owner = request.form.get("owner")
    due_date_str = request.form.get("due_date")
    if not title:
        return redirect(url_for("main.view_risk", risk_id=risk.id))
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except Exception:
            due_date = None
    m = Mitigation(risk_id=risk.id, title=title, description=description, owner=owner, due_date=due_date)
    db.session.add(m)
    # Try auto-update risk state
    try:
        risk.recompute_status_from_mitigations()
    except Exception:
        pass
    db.session.commit()
    return redirect(url_for("main.view_risk", risk_id=risk.id))

@bp.route("/mitigations/<int:mitigation_id>/transition", methods=["POST"]) 
def transition_mitigation_ui(mitigation_id):
    m = Mitigation.query.get_or_404(mitigation_id)
    to_status = request.form.get("to_status")
    try:
        m.transition(to_status)
        # After mitigation state change, recompute risk state heuristics
        m.risk.recompute_status_from_mitigations()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return render_template("risk_detail.html", risk=m.risk, error=str(e)), 400
    return redirect(url_for("main.view_risk", risk_id=m.risk_id))

# -------- API Routes --------

def ok(data=None, status=200):
    return jsonify({"ok": True, "data": data}), status

def err(message, status=400):
    return jsonify({"ok": False, "error": message}), status

@bp.route("/api/ideas", methods=["GET"]) 
def api_list_ideas():
    ideas = Idea.query.order_by(Idea.created_at.desc()).all()
    return ok([i.to_dict() for i in ideas])

@bp.route("/api/ideas", methods=["POST"]) 
def api_create_idea():
    payload = request.get_json(force=True, silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return err("title is required", 422)
    idea = Idea(title=title, description=payload.get("description"))
    db.session.add(idea)
    db.session.commit()
    return ok(idea.to_dict(), 201)

@bp.route("/api/ideas/<int:idea_id>", methods=["GET"]) 
def api_get_idea(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    data = idea.to_dict()
    data["risks"] = [r.to_dict() for r in idea.risks]
    return ok(data)

@bp.route("/api/ideas/<int:idea_id>/risks", methods=["GET"]) 
def api_list_risks_for_idea(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    risks = Risk.query.filter_by(idea_id=idea.id).order_by(Risk.created_at.desc()).all()
    return ok([r.to_dict() for r in risks])

@bp.route("/api/risks", methods=["POST"]) 
def api_create_risk():
    payload = request.get_json(force=True, silent=True) or {}
    idea_id = payload.get("idea_id")
    if not idea_id:
        return err("idea_id is required", 422)
    if not Idea.query.get(idea_id):
        return err("idea not found", 404)
    title = (payload.get("title") or "").strip()
    if not title:
        return err("title is required", 422)
    severity = int(payload.get("severity", 3))
    likelihood = int(payload.get("likelihood", 3))
    severity = min(5, max(1, severity))
    likelihood = min(5, max(1, likelihood))
    risk = Risk(
        idea_id=idea_id,
        title=title,
        description=payload.get("description"),
        owner=payload.get("owner"),
        severity=severity,
        likelihood=likelihood,
    )
    db.session.add(risk)
    db.session.commit()
    return ok(risk.to_dict(), 201)

@bp.route("/api/risks/<int:risk_id>", methods=["GET"]) 
def api_get_risk(risk_id):
    risk = Risk.query.get_or_404(risk_id)
    return ok(risk.to_dict(include_related=True))

@bp.route("/api/risks/<int:risk_id>/transition", methods=["POST"]) 
def api_transition_risk(risk_id):
    risk = Risk.query.get_or_404(risk_id)
    payload = request.get_json(force=True, silent=True) or {}
    to_state = payload.get("to_state")
    actor = payload.get("actor") or "api"
    note = payload.get("note")
    try:
        risk.transition(to_state, actor=actor, note=note)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return err(str(e), 400)
    return ok(risk.to_dict())

@bp.route("/api/risks/<int:risk_id>/mitigations", methods=["POST"]) 
def api_add_mitigation(risk_id):
    risk = Risk.query.get_or_404(risk_id)
    payload = request.get_json(force=True, silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return err("title is required", 422)
    m = Mitigation(
        risk_id=risk.id,
        title=title,
        description=payload.get("description"),
        owner=payload.get("owner"),
    )
    db.session.add(m)
    try:
        risk.recompute_status_from_mitigations()
    except Exception:
        pass
    db.session.commit()
    return ok(m.to_dict(), 201)

@bp.route("/api/mitigations/<int:mitigation_id>/transition", methods=["POST"]) 
def api_transition_mitigation(mitigation_id):
    m = Mitigation.query.get_or_404(mitigation_id)
    payload = request.get_json(force=True, silent=True) or {}
    to_status = payload.get("to_status")
    try:
        m.transition(to_status)
        m.risk.recompute_status_from_mitigations()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return err(str(e), 400)
    return ok({"mitigation": m.to_dict(), "risk": m.risk.to_dict()})

@bp.route("/api/risks/<int:risk_id>/events", methods=["GET"]) 
def api_risk_events(risk_id):
    risk = Risk.query.get_or_404(risk_id)
    return ok([e.to_dict() for e in risk.events])

