from datetime import datetime
from flask import Blueprint, jsonify, request
from .extensions import db
from .models import User, AuditEvent, AuditDataChange
from .audit import audit_user_action, verify_chain

bp = Blueprint("api", __name__)


# Example CRUD to generate data changes
@bp.route("/users", methods=["POST"])
def create_user():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    full_name = data.get("full_name")
    if not email:
        return jsonify({"error": "email required"}), 400
    u = User(email=email, full_name=full_name)
    db.session.add(u)
    db.session.commit()
    audit_user_action("user_created", {"user_id": u.id, "email": u.email})
    return jsonify({"id": u.id, "email": u.email, "full_name": u.full_name}), 201


@bp.route("/users/<user_id>", methods=["PUT"])
def update_user(user_id):
    u = db.session.get(User, user_id)
    if not u:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    if "email" in data:
        u.email = data["email"]
    if "full_name" in data:
        u.full_name = data["full_name"]
    db.session.commit()
    audit_user_action("user_updated", {"user_id": u.id})
    return jsonify({"id": u.id, "email": u.email, "full_name": u.full_name})


@bp.route("/users/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    u = db.session.get(User, user_id)
    if not u:
        return jsonify({"error": "not found"}), 404
    db.session.delete(u)
    db.session.commit()
    audit_user_action("user_deleted", {"user_id": user_id})
    return jsonify({"status": "deleted"})


# Compliance report endpoints
@bp.route("/reports/compliance", methods=["GET"])
def compliance_report():
    # Filters: user_id, event_type, action, since, until, limit
    user_id = request.args.get("user_id")
    event_type = request.args.get("event_type")
    action = request.args.get("action")
    since = request.args.get("since")
    until = request.args.get("until")
    limit = request.args.get("limit", type=int)

    q = db.session.query(AuditEvent).order_by(AuditEvent.created_at.desc())
    if user_id:
        q = q.filter(AuditEvent.user_id == user_id)
    if event_type:
        q = q.filter(AuditEvent.event_type == event_type)
    if action:
        q = q.filter(AuditEvent.action == action)
    if since:
        try:
            dt = datetime.fromisoformat(since)
            q = q.filter(AuditEvent.created_at >= dt)
        except Exception:
            return jsonify({"error": "invalid since, use ISO-8601"}), 400
    if until:
        try:
            dt = datetime.fromisoformat(until)
            q = q.filter(AuditEvent.created_at <= dt)
        except Exception:
            return jsonify({"error": "invalid until, use ISO-8601"}), 400
    if limit:
        q = q.limit(limit)

    events = q.all()

    result = []
    for ev in events:
        item = {
            "id": ev.id,
            "created_at": ev.created_at.isoformat(),
            "user_id": ev.user_id,
            "request_id": ev.request_id,
            "ip": ev.ip,
            "event_type": ev.event_type,
            "action": ev.action,
            "method": ev.method,
            "path": ev.path,
            "status_code": ev.status_code,
            "details": ev.details,
            "previous_hash": ev.previous_hash,
            "event_hash": ev.event_hash,
            "hmac_signature": ev.hmac_signature,
        }
        if ev.event_type == "data_change":
            changes = db.session.query(AuditDataChange).filter_by(event_id=ev.id).all()
            item["data_changes"] = [
                {
                    "table_name": c.table_name,
                    "row_pk": c.row_pk,
                    "operation": c.operation,
                    "before_data": c.before_data,
                    "after_data": c.after_data,
                }
                for c in changes
            ]
        result.append(item)

    # Include integrity check summary
    integrity = verify_chain(limit=limit)

    return jsonify({"integrity": integrity, "events": result})


@bp.route("/reports/verify", methods=["GET"])
def verify_report():
    limit = request.args.get("limit", type=int)
    since = request.args.get("since")
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except Exception:
            return jsonify({"error": "invalid since, use ISO-8601"}), 400
    result = verify_chain(limit=limit, since=since_dt)
    return jsonify(result)

