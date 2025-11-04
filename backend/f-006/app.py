import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request, abort

from models import db, Runbook, EscalationPolicy, Alert, Incident, IncidentNotification


DEFAULT_WORKER_INTERVAL = int(os.getenv("ESCALATION_WORKER_INTERVAL_SECONDS", "5"))


def utcnow():
    return datetime.now(timezone.utc)


def create_app() -> Flask:
    app = Flask(__name__)

    # Basic config
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JSON_SORT_KEYS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_defaults()

    # Routes
    register_routes(app)

    # Start escalation worker
    start_escalation_worker(app)

    return app


def seed_defaults():
    if Runbook.query.count() == 0:
        rb = Runbook(
            name="Service X - High CPU Runbook",
            url="https://wiki.example.com/runbooks/service-x-cpu",
            description="Steps to diagnose and mitigate high CPU on Service X.",
        )
        db.session.add(rb)
        db.session.commit()

    if EscalationPolicy.query.count() == 0:
        # Simple 3-level policy
        policy = EscalationPolicy(
            name="Default 3-level",
            description="Default policy escalating from primary on-call to team lead.",
            levels=[
                {"delay_seconds": 0, "targets": ["primary-oncall@example.com"]},
                {"delay_minutes": 5, "targets": ["secondary-oncall@example.com", "team-chat@example.com"]},
                {"delay_minutes": 15, "targets": ["eng-manager@example.com"]},
            ],
        )
        db.session.add(policy)
        db.session.commit()

    if Alert.query.count() == 0:
        rb = Runbook.query.first()
        policy = EscalationPolicy.query.first()
        alert = Alert(
            name="Service X - High CPU",
            severity="critical",
            runbook_id=rb.id,
            policy_id=policy.id,
        )
        db.session.add(alert)
        db.session.commit()


# Utility: convert string id to model or 404

def get_or_404(model, id_value):
    obj = model.query.get(id_value)
    if not obj:
        abort(404, description=f"{model.__name__} not found")
    return obj


# Worker

def start_escalation_worker(app: Flask):
    def worker_loop():
        # Run until process exits
        while True:
            try:
                with app.app_context():
                    process_escalations()
            except Exception as e:
                # Log simple error; in production use proper logger
                print(f"[EscalationWorker] Error: {e}")
            time.sleep(DEFAULT_WORKER_INTERVAL)

    t = threading.Thread(target=worker_loop, name="EscalationWorker", daemon=True)
    t.start()


def process_escalations():
    now = utcnow()
    open_incidents: List[Incident] = (
        Incident.query.filter(Incident.status == "open").all()
    )
    for inc in open_incidents:
        levels: List[Dict[str, Any]] = inc.policy_levels or []
        next_level_index = (inc.current_level or -1) + 1
        if next_level_index >= len(levels):
            continue  # No more levels
        # Determine delay
        level_conf = levels[next_level_index]
        delay_seconds = int(level_conf.get("delay_seconds") or level_conf.get("delay_minutes", 0) * 60)
        base_time = inc.last_escalated_at or inc.created_at
        elapsed = (now - base_time).total_seconds()
        if elapsed >= delay_seconds:
            # Escalate now
            targets = level_conf.get("targets", [])
            message = f"Incident {inc.id} escalation to level {next_level_index}: targets={targets}. Runbook: {inc.runbook_url or 'n/a'}"
            simulate_notifications(inc, next_level_index, targets, message)
            inc.current_level = next_level_index
            inc.last_escalated_at = now
            inc.updated_at = now
            db.session.add(inc)
            db.session.commit()


def simulate_notifications(incident: Incident, level_index: int, targets: List[str], message: str):
    now = utcnow()
    for tgt in targets:
        print(f"[Notify] {now.isoformat()} -> {tgt}: {message}")
        notif = IncidentNotification(
            incident_id=incident.id,
            level=level_index,
            target=tgt,
            notified_via="simulated",
            sent_at=now,
            status="sent",
            message=message,
        )
        db.session.add(notif)
    db.session.commit()


# Routes registration

def register_routes(app: Flask):
    @app.route("/")
    def index():
        return jsonify({
            "service": "Alert Escalation & Incidents API",
            "endpoints": [
                "/api/runbooks",
                "/api/policies",
                "/api/alerts",
                "/api/alerts/<id>/trigger",
                "/api/incidents",
                "/api/incidents/<id>/acknowledge",
                "/api/incidents/<id>/resolve",
            ],
        })

    # Runbooks CRUD
    @app.route("/api/runbooks", methods=["GET"])  
    def list_runbooks():
        items = Runbook.query.order_by(Runbook.created_at.desc()).all()
        return jsonify([i.to_dict() for i in items])

    @app.route("/api/runbooks", methods=["POST"])  
    def create_runbook():
        data = request.get_json(force=True) or {}
        name = data.get("name")
        url = data.get("url")
        if not name or not url:
            abort(400, description="name and url are required")
        rb = Runbook(name=name, url=url, description=data.get("description"))
        db.session.add(rb)
        db.session.commit()
        return jsonify(rb.to_dict()), 201

    @app.route("/api/runbooks/<int:rb_id>", methods=["GET"])  
    def get_runbook(rb_id):
        rb = get_or_404(Runbook, rb_id)
        return jsonify(rb.to_dict())

    @app.route("/api/runbooks/<int:rb_id>", methods=["PUT","PATCH"])  
    def update_runbook(rb_id):
        rb = get_or_404(Runbook, rb_id)
        data = request.get_json(force=True) or {}
        if "name" in data:
            rb.name = data["name"]
        if "url" in data:
            rb.url = data["url"]
        if "description" in data:
            rb.description = data["description"]
        rb.updated_at = utcnow()
        db.session.add(rb)
        db.session.commit()
        return jsonify(rb.to_dict())

    @app.route("/api/runbooks/<int:rb_id>", methods=["DELETE"])  
    def delete_runbook(rb_id):
        rb = get_or_404(Runbook, rb_id)
        db.session.delete(rb)
        db.session.commit()
        return jsonify({"deleted": True})

    # Policies CRUD
    @app.route("/api/policies", methods=["GET"])  
    def list_policies():
        items = EscalationPolicy.query.order_by(EscalationPolicy.created_at.desc()).all()
        return jsonify([i.to_dict() for i in items])

    @app.route("/api/policies", methods=["POST"])  
    def create_policy():
        data = request.get_json(force=True) or {}
        name = data.get("name")
        levels = data.get("levels")
        if not name or not isinstance(levels, list):
            abort(400, description="name and levels(list) are required")
        policy = EscalationPolicy(
            name=name,
            description=data.get("description"),
            levels=levels,
        )
        db.session.add(policy)
        db.session.commit()
        return jsonify(policy.to_dict()), 201

    @app.route("/api/policies/<int:pid>", methods=["GET"])  
    def get_policy(pid):
        policy = get_or_404(EscalationPolicy, pid)
        return jsonify(policy.to_dict())

    @app.route("/api/policies/<int:pid>", methods=["PUT","PATCH"])  
    def update_policy(pid):
        policy = get_or_404(EscalationPolicy, pid)
        data = request.get_json(force=True) or {}
        if "name" in data:
            policy.name = data["name"]
        if "description" in data:
            policy.description = data["description"]
        if "levels" in data:
            if not isinstance(data["levels"], list):
                abort(400, description="levels must be a list")
            policy.levels = data["levels"]
        policy.updated_at = utcnow()
        db.session.add(policy)
        db.session.commit()
        return jsonify(policy.to_dict())

    @app.route("/api/policies/<int:pid>", methods=["DELETE"])  
    def delete_policy(pid):
        policy = get_or_404(EscalationPolicy, pid)
        db.session.delete(policy)
        db.session.commit()
        return jsonify({"deleted": True})

    # Alerts CRUD
    @app.route("/api/alerts", methods=["GET"])  
    def list_alerts():
        items = Alert.query.order_by(Alert.created_at.desc()).all()
        return jsonify([i.to_dict() for i in items])

    @app.route("/api/alerts", methods=["POST"])  
    def create_alert():
        data = request.get_json(force=True) or {}
        name = data.get("name")
        severity = data.get("severity", "info")
        policy_id = data.get("policy_id")
        runbook_id = data.get("runbook_id")
        if not name or not policy_id or not runbook_id:
            abort(400, description="name, policy_id, runbook_id are required")
        # Validate FKs
        get_or_404(EscalationPolicy, policy_id)
        get_or_404(Runbook, runbook_id)
        alert = Alert(name=name, severity=severity, policy_id=policy_id, runbook_id=runbook_id)
        db.session.add(alert)
        db.session.commit()
        return jsonify(alert.to_dict()), 201

    @app.route("/api/alerts/<int:aid>", methods=["GET"])  
    def get_alert(aid):
        alert = get_or_404(Alert, aid)
        return jsonify(alert.to_dict())

    @app.route("/api/alerts/<int:aid>", methods=["PUT","PATCH"])  
    def update_alert(aid):
        alert = get_or_404(Alert, aid)
        data = request.get_json(force=True) or {}
        if "name" in data:
            alert.name = data["name"]
        if "severity" in data:
            alert.severity = data["severity"]
        if "policy_id" in data:
            get_or_404(EscalationPolicy, data["policy_id"])  # validate
            alert.policy_id = data["policy_id"]
        if "runbook_id" in data:
            get_or_404(Runbook, data["runbook_id"])  # validate
            alert.runbook_id = data["runbook_id"]
        alert.updated_at = utcnow()
        db.session.add(alert)
        db.session.commit()
        return jsonify(alert.to_dict())

    @app.route("/api/alerts/<int:aid>", methods=["DELETE"])  
    def delete_alert(aid):
        alert = get_or_404(Alert, aid)
        db.session.delete(alert)
        db.session.commit()
        return jsonify({"deleted": True})

    # Trigger alert to create incident automatically
    @app.route("/api/alerts/<int:aid>/trigger", methods=["POST"])  
    def trigger_alert(aid):
        alert = get_or_404(Alert, aid)
        inc = create_incident_from_alert(alert)
        return jsonify(inc.to_dict(include_notifications=True)), 201

    # Incidents
    @app.route("/api/incidents", methods=["GET"])  
    def list_incidents():
        status = request.args.get("status")
        q = Incident.query
        if status:
            q = q.filter(Incident.status == status)
        items = q.order_by(Incident.created_at.desc()).all()
        return jsonify([i.to_dict() for i in items])

    @app.route("/api/incidents/<int:inc_id>", methods=["GET"])  
    def get_incident(inc_id):
        inc = get_or_404(Incident, inc_id)
        return jsonify(inc.to_dict(include_notifications=True))

    @app.route("/api/incidents/<int:inc_id>/acknowledge", methods=["POST"])  
    def acknowledge_incident(inc_id):
        inc = get_or_404(Incident, inc_id)
        if inc.status != "open":
            abort(400, description="Incident is not open")
        inc.status = "acknowledged"
        inc.acknowledged_at = utcnow()
        inc.updated_at = inc.acknowledged_at
        db.session.add(inc)
        db.session.commit()
        return jsonify(inc.to_dict())

    @app.route("/api/incidents/<int:inc_id>/resolve", methods=["POST"])  
    def resolve_incident(inc_id):
        inc = get_or_404(Incident, inc_id)
        if inc.status not in ("open", "acknowledged"):
            abort(400, description="Incident is not active")
        inc.status = "resolved"
        inc.resolved_at = utcnow()
        inc.updated_at = inc.resolved_at
        db.session.add(inc)
        db.session.commit()
        return jsonify(inc.to_dict())

    # Direct creation of incident from payload (optional)
    @app.route("/api/incidents/from_alert", methods=["POST"])  
    def create_incident_from_alert_endpoint():
        data = request.get_json(force=True) or {}
        alert_id = data.get("alert_id")
        alert_name = data.get("alert_name")
        alert: Alert | None = None
        if alert_id:
            alert = get_or_404(Alert, alert_id)
        elif alert_name:
            alert = Alert.query.filter_by(name=alert_name).first()
            if not alert:
                abort(404, description="Alert with given name not found")
        else:
            abort(400, description="alert_id or alert_name is required")
        inc = create_incident_from_alert(alert)
        return jsonify(inc.to_dict(include_notifications=True)), 201


# Logic to create incident

def create_incident_from_alert(alert: Alert) -> Incident:
    # Snapshot policy
    policy: EscalationPolicy = EscalationPolicy.query.get(alert.policy_id)
    runbook: Runbook = Runbook.query.get(alert.runbook_id)
    now = utcnow()
    inc = Incident(
        alert_id=alert.id,
        status="open",
        current_level=-1,
        created_at=now,
        updated_at=now,
        last_escalated_at=None,
        acknowledged_at=None,
        resolved_at=None,
        runbook_url=runbook.url if runbook else None,
        policy_name=policy.name if policy else None,
        policy_levels=(policy.levels if policy else []),
        alert_snapshot={"name": alert.name, "severity": alert.severity},
    )
    db.session.add(inc)
    db.session.commit()
    return inc


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

