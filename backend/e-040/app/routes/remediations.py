from datetime import datetime
from flask import Blueprint, request, jsonify
from ..db import db
from ..models import Remediation, RemediationAction, Finding, Rule

remediations_bp = Blueprint('remediations', __name__)


def parse_dt(dt_str):
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except Exception:
        return None


@remediations_bp.get("")
def list_remediations():
    q = Remediation.query
    status = request.args.get('status')
    if status:
        q = q.filter(Remediation.status == status)
    owner = request.args.get('owner')
    if owner:
        q = q.filter(Remediation.owner == owner)
    return jsonify([r.to_dict(include_actions=False) for r in q.order_by(Remediation.created_at.desc()).all()])


@remediations_bp.get("/<rem_id>")
def get_remediation(rem_id):
    r = Remediation.query.get_or_404(rem_id)
    return jsonify(r.to_dict())


@remediations_bp.post("")
def create_remediation():
    data = request.get_json(force=True)
    finding_ids = data.get('finding_ids') or []
    if not finding_ids:
        return jsonify({'error': 'missing_finding_ids'}), 400

    findings = Finding.query.filter(Finding.id.in_(finding_ids)).all()
    if not findings:
        return jsonify({'error': 'no_valid_findings'}), 400

    rem = Remediation(
        status=data.get('status') or 'Planned',
        owner=data.get('owner'),
        due_date=parse_dt(data.get('due_date')),
        summary=data.get('summary') or 'Auto-generated remediation plan',
        notes=data.get('notes')
    )
    db.session.add(rem)
    db.session.flush()

    # Create actions
    for f in findings:
        rule = Rule.query.get(f.rule_id)
        action_text = rule.remediation_guidance if rule and rule.remediation_guidance else f"Remediate finding for rule {rule.key if rule else f.rule_id} on asset {f.asset_id}"
        act = RemediationAction(
            remediation_id=rem.id,
            finding_id=f.id,
            action=action_text,
            status='Pending'
        )
        db.session.add(act)

    db.session.commit()
    return jsonify(rem.to_dict()), 201


@remediations_bp.patch("/<rem_id>")
def update_remediation(rem_id):
    rem = Remediation.query.get_or_404(rem_id)
    data = request.get_json(force=True)
    changed = False
    for field in ['status', 'owner', 'summary', 'notes']:
        if field in data:
            setattr(rem, field, data[field])
            changed = True
    if 'due_date' in data:
        rem.due_date = parse_dt(data.get('due_date'))
        changed = True
    if changed:
        db.session.commit()
    return jsonify(rem.to_dict())


@remediations_bp.post("/<rem_id>/actions/<act_id>")
def update_action(rem_id, act_id):
    rem = Remediation.query.get_or_404(rem_id)
    act = next((a for a in rem.actions if a.id == act_id), None)
    if not act:
        return jsonify({'error': 'action_not_found'}), 404
    data = request.get_json(force=True)
    if 'status' in data:
        act.status = data['status']
        act.updated_at = datetime.utcnow()
    if 'action' in data:
        act.action = data['action']
        act.updated_at = datetime.utcnow()
    db.session.commit()

    # Auto-resolve finding if action done
    if act.status == 'Done':
        f = Finding.query.get(act.finding_id)
        if f and f.status != 'Resolved':
            f.status = 'Resolved'
            db.session.commit()

    return jsonify(act.to_dict())

