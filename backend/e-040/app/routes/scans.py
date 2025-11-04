from datetime import datetime
from flask import Blueprint, request, jsonify
from ..db import db
from ..models import Scan, Asset, Rule, Finding

scans_bp = Blueprint('scans', __name__)


def parse_dt(dt_str):
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except Exception:
        return None


@scans_bp.post("")
def create_scan():
    data = request.get_json(force=True, silent=True) or {}
    scan = Scan(
        provider=data.get('provider'),
        status=data.get('status') or 'Running'
    )
    db.session.add(scan)
    db.session.commit()
    return jsonify(scan.to_dict()), 201


@scans_bp.get("")
def list_scans():
    q = Scan.query.order_by(Scan.started_at.desc())
    provider = request.args.get('provider')
    if provider:
        q = q.filter(Scan.provider == provider)
    status = request.args.get('status')
    if status:
        q = q.filter(Scan.status == status)
    return jsonify([s.to_dict() for s in q.all()])


@scans_bp.get("/<scan_id>")
def get_scan(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    return jsonify(scan.to_dict())


@scans_bp.post("/<scan_id>/finalize")
def finalize_scan(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    data = request.get_json(force=True, silent=True) or {}
    scan.status = data.get('status') or 'Completed'
    scan.finished_at = parse_dt(data.get('finished_at')) or datetime.utcnow()
    db.session.commit()
    return jsonify(scan.to_dict())


@scans_bp.post("/<scan_id>/ingest")
def ingest_scan(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    payload = request.get_json(force=True)
    assets = payload.get('assets') or []
    findings = payload.get('findings') or []

    # Upsert assets
    asset_map = {}
    for a in assets:
        aid = a.get('id')
        if aid:
            existing = Asset.query.get(aid)
        else:
            existing = None
        if existing:
            existing.name = a.get('name') or existing.name
            existing.type = a.get('type') or existing.type
            existing.provider = a.get('provider') or existing.provider
            existing.region = a.get('region') or existing.region
            if a.get('tags'):
                existing.tags = a.get('tags')
            asset = existing
        else:
            if not a.get('name') or not a.get('type') or not a.get('provider'):
                return jsonify({'error': 'asset_missing_required_fields'}), 400
            asset = Asset(
                id=aid,
                name=a['name'],
                type=a['type'],
                provider=a['provider'],
                region=a.get('region'),
                tags=a.get('tags') or {}
            )
            db.session.add(asset)
        asset_map[asset.id] = asset

    # Upsert rules by key
    rule_cache = {r.key: r for r in Rule.query.all()}

    created_findings = []
    for f in findings:
        asset_id = f.get('asset_id')
        if not asset_id:
            return jsonify({'error': 'finding_missing_asset_id'}), 400
        if asset_id not in asset_map:
            # attempt fetch from DB if not in current assets payload
            asset_obj = Asset.query.get(asset_id)
            if not asset_obj:
                return jsonify({'error': f'unknown_asset:{asset_id}'}), 400
            asset_map[asset_id] = asset_obj

        rule_payload = f.get('rule') or {}
        rule_key = rule_payload.get('key')
        if not rule_key:
            return jsonify({'error': 'finding_missing_rule_key'}), 400
        rule_obj = rule_cache.get(rule_key)
        if not rule_obj:
            rule_obj = Rule(
                key=rule_key,
                title=rule_payload.get('title') or rule_key,
                severity=rule_payload.get('severity') or 'Medium',
                description=rule_payload.get('description'),
                remediation_guidance=rule_payload.get('remediation_guidance'),
                service=rule_payload.get('service'),
                query=rule_payload.get('query')
            )
            db.session.add(rule_obj)
            db.session.flush()
            rule_cache[rule_key] = rule_obj

        finding = Finding(
            scan_id=scan.id,
            asset_id=asset_id,
            rule_id=rule_obj.id,
            status=f.get('status') or 'Open',
            state=f.get('state') or 'Fail',
            severity=rule_obj.severity,
            observed_at=parse_dt(f.get('observed_at')) or datetime.utcnow(),
            details=f.get('details') or {},
            evidence=f.get('evidence'),
            rationale=f.get('rationale')
        )
        db.session.add(finding)
        created_findings.append(finding)

    scan.asset_count = len(asset_map)
    db.session.commit()

    resp = {
        'scan': scan.to_dict(),
        'assets': [a.to_dict() for a in asset_map.values()],
        'findings': [x.to_dict() for x in created_findings]
    }
    return jsonify(resp), 201

