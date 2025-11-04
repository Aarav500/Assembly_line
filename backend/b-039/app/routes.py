from datetime import datetime, timedelta
from typing import Optional
from flask import Blueprint, jsonify, request
from .models import db, Idea, Policy
from .maintenance import run_maintenance_once, get_effective_policy

api_bp = Blueprint("api", __name__)


def parse_iso_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        # Accept both with or without trailing Z
        v = value.rstrip("Z")
        dt = datetime.fromisoformat(v)
        return dt
    except Exception:
        return None


@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# Policies endpoints
@api_bp.route("/policies", methods=["GET"])  # list
def list_policies():
    active = request.args.get("active")
    q = Policy.query
    if active is not None:
        q = q.filter(Policy.active == (active in ("1", "true", "True")))
    items = q.order_by(Policy.id.asc()).all()
    return jsonify([p.to_dict() for p in items])


@api_bp.route("/policies", methods=["POST"])  # create
def create_policy():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400
    if Policy.query.filter_by(name=name).first():
        return jsonify({"error": "policy with that name exists"}), 400
    pol = Policy(
        name=name,
        description=data.get("description"),
        auto_archive_after_days=data.get("auto_archive_after_days"),
        auto_purge_after_days=data.get("auto_purge_after_days"),
        purge_hard=bool(data.get("purge_hard", False)),
        active=bool(data.get("active", True)),
    )
    db.session.add(pol)
    db.session.commit()
    return jsonify(pol.to_dict()), 201


@api_bp.route("/policies/<int:pid>", methods=["GET"])  # retrieve
def get_policy(pid: int):
    pol = Policy.query.get_or_404(pid)
    return jsonify(pol.to_dict())


@api_bp.route("/policies/<int:pid>", methods=["PATCH"])  # update
def update_policy(pid: int):
    pol = Policy.query.get_or_404(pid)
    data = request.get_json(force=True, silent=True) or {}

    for field in [
        "name",
        "description",
        "auto_archive_after_days",
        "auto_purge_after_days",
        "purge_hard",
        "active",
    ]:
        if field in data:
            setattr(pol, field, data[field])

    db.session.add(pol)
    db.session.commit()
    return jsonify(pol.to_dict())


@api_bp.route("/policies/<int:pid>", methods=["DELETE"])  # delete/inactivate
def delete_policy(pid: int):
    pol = Policy.query.get_or_404(pid)
    db.session.delete(pol)
    db.session.commit()
    return ("", 204)


# Ideas endpoints
@api_bp.route("/ideas", methods=["GET"])  # list
def list_ideas():
    status = request.args.get("status")  # active|archived|purged|all
    q = Idea.query
    if status and status != "all":
        q = q.filter(Idea.status == status)
    elif status != "all":
        # By default, exclude purged
        q = q.filter(Idea.status != "purged")

    items = q.order_by(Idea.id.desc()).all()
    return jsonify([i.to_dict() for i in items])


@api_bp.route("/ideas", methods=["POST"])  # create
def create_idea():
    data = request.get_json(force=True, silent=True) or {}
    title = data.get("title")
    if not title:
        return jsonify({"error": "title is required"}), 400

    idea = Idea(
        title=title,
        content=data.get("content"),
        policy_id=data.get("policy_id"),
        purge_hard_override=data.get("purge_hard_override"),
    )

    # Expiration handling
    expires_at = None
    if data.get("expires_at"):
        expires_at = parse_iso_datetime(data.get("expires_at"))
        if not expires_at:
            return jsonify({"error": "invalid expires_at"}), 400
    elif data.get("expires_in_days") is not None:
        try:
            days = int(data.get("expires_in_days"))
            expires_at = datetime.utcnow() + timedelta(days=days)
        except Exception:
            return jsonify({"error": "invalid expires_in_days"}), 400
    idea.expires_at = expires_at

    db.session.add(idea)
    db.session.commit()
    return jsonify(idea.to_dict()), 201


@api_bp.route("/ideas/<int:iid>", methods=["GET"])  # retrieve
def get_idea(iid: int):
    idea = Idea.query.get_or_404(iid)
    return jsonify(idea.to_dict())


@api_bp.route("/ideas/<int:iid>", methods=["PATCH"])  # update or actions
def update_idea(iid: int):
    idea = Idea.query.get_or_404(iid)
    data = request.get_json(force=True, silent=True) or {}

    action = data.get("action")
    now = datetime.utcnow()

    if action == "archive":
        if idea.status == "active":
            idea.status = "archived"
            idea.archived_at = now
        db.session.commit()
        return jsonify(idea.to_dict())
    elif action == "purge":
        hard = data.get("hard")
        if hard is None:
            # Derive from effective settings
            hard = False
            pol = get_effective_policy(idea)
            if idea.purge_hard_override is not None:
                hard = bool(idea.purge_hard_override)
            elif pol:
                hard = bool(pol.purge_hard)
        if hard:
            db.session.delete(idea)
            db.session.commit()
            return ("", 204)
        else:
            idea.status = "purged"
            idea.purged_at = now
            idea.content = None
            idea.title = f"[Purged #{idea.id}]"
            db.session.commit()
            return jsonify(idea.to_dict())

    # Regular updates
    for field in ["title", "content", "policy_id", "purge_hard_override"]:
        if field in data:
            setattr(idea, field, data[field])

    if "expires_at" in data:
        if data["expires_at"] is None:
            idea.expires_at = None
        else:
            dt = parse_iso_datetime(data["expires_at"])
            if not dt:
                return jsonify({"error": "invalid expires_at"}), 400
            idea.expires_at = dt

    if "expires_in_days" in data and data["expires_in_days"] is not None:
        try:
            days = int(data["expires_in_days"])
            idea.expires_at = datetime.utcnow() + timedelta(days=days)
        except Exception:
            return jsonify({"error": "invalid expires_in_days"}), 400

    db.session.add(idea)
    db.session.commit()
    return jsonify(idea.to_dict())


@api_bp.route("/ideas/<int:iid>", methods=["DELETE"])  # purge via DELETE
def delete_idea(iid: int):
    idea = Idea.query.get_or_404(iid)
    hard_param = request.args.get("hard")
    hard: Optional[bool] = None
    if hard_param is not None:
        hard = hard_param in ("1", "true", "True")

    now = datetime.utcnow()
    if hard is None:
        # default to effective setting
        pol = get_effective_policy(idea)
        if idea.purge_hard_override is not None:
            hard = bool(idea.purge_hard_override)
        elif pol:
            hard = bool(pol.purge_hard)
        else:
            hard = False

    if hard:
        db.session.delete(idea)
        db.session.commit()
        return ("", 204)
    else:
        idea.status = "purged"
        idea.purged_at = now
        idea.content = None
        idea.title = f"[Purged #{idea.id}]"
        db.session.commit()
        return jsonify(idea.to_dict())


# Manual maintenance trigger
@api_bp.route("/admin/run-maintenance", methods=["POST"])
def manual_maintenance():
    res = run_maintenance_once()
    return jsonify(res)

