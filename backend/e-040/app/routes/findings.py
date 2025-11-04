from flask import Blueprint, request, jsonify
from ..db import db
from ..models import Finding

findings_bp = Blueprint('findings', __name__)


@findings_bp.get("")
def list_findings():
    q = Finding.query
    for key in ['status', 'state', 'severity', 'rule_id', 'asset_id', 'scan_id']:
        val = request.args.get(key)
        if val:
            q = q.filter(getattr(Finding, key) == val)
    limit = min(int(request.args.get('limit', 200)), 1000)
    findings = q.order_by(Finding.observed_at.desc()).limit(limit).all()
    return jsonify([f.to_dict() for f in findings])


@findings_bp.get("/<finding_id>")
def get_finding(finding_id):
    f = Finding.query.get_or_404(finding_id)
    return jsonify(f.to_dict())


@findings_bp.patch("/<finding_id>")
def update_finding(finding_id):
    f = Finding.query.get_or_404(finding_id)
    data = request.get_json(force=True)
    changed = False
    if 'status' in data:
        f.status = data['status']
        changed = True
    if 'rationale' in data:
        f.rationale = data['rationale']
        changed = True
    if 'evidence' in data:
        f.evidence = data['evidence']
        changed = True
    if changed:
        db.session.commit()
    return jsonify(f.to_dict())


@findings_bp.post("/bulk-update")
def bulk_update_findings():
    data = request.get_json(force=True)
    ids = data.get('finding_ids') or []
    if not ids:
        return jsonify({'error': 'missing_finding_ids'}), 400
    updates = {}
    for field in ['status', 'rationale']:
        if field in data:
            updates[field] = data[field]
    updated = []
    for fid in ids:
        f = Finding.query.get(fid)
        if not f:
            continue
        for k, v in updates.items():
            setattr(f, k, v)
        updated.append(f)
    db.session.commit()
    return jsonify({'updated': [f.to_dict() for f in updated]})

