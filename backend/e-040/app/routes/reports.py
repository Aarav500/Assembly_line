from flask import Blueprint, jsonify
from sqlalchemy import func
from ..db import db
from ..models import Finding, Asset, Rule

reports_bp = Blueprint('reports', __name__)


@reports_bp.get("/compliance-summary")
def compliance_summary():
    # counts by state and severity
    state_counts = (
        db.session.query(Finding.state, func.count(Finding.id))
        .group_by(Finding.state)
        .all()
    )
    severity_counts = (
        db.session.query(Finding.severity, func.count(Finding.id))
        .group_by(Finding.severity)
        .all()
    )
    status_counts = (
        db.session.query(Finding.status, func.count(Finding.id))
        .group_by(Finding.status)
        .all()
    )

    by_rule = (
        db.session.query(Rule.key, Rule.title, Finding.state, func.count(Finding.id))
        .join(Rule, Finding.rule_id == Rule.id)
        .group_by(Rule.key, Rule.title, Finding.state)
        .all()
    )
    rule_summary = {}
    for key, title, state, cnt in by_rule:
        if key not in rule_summary:
            rule_summary[key] = {"key": key, "title": title, "Pass": 0, "Fail": 0}
        rule_summary[key][state] = cnt

    return jsonify({
        'states': {k: v for k, v in state_counts},
        'severities': {k: v for k, v in severity_counts},
        'statuses': {k: v for k, v in status_counts},
        'rules': list(rule_summary.values())
    })


@reports_bp.get("/assets")
def asset_report():
    # Counts per asset
    rows = (
        db.session.query(Asset.id, Asset.name, func.sum(func.case([(Finding.state == 'Fail', 1)], else_=0)), func.sum(func.case([(Finding.state == 'Pass', 1)], else_=0)))
        .outerjoin(Finding, Finding.asset_id == Asset.id)
        .group_by(Asset.id, Asset.name)
        .all()
    )
    res = []
    for aid, name, fails, passes in rows:
        res.append({
            'asset_id': aid,
            'asset_name': name,
            'failures': int(fails or 0),
            'passes': int(passes or 0)
        })
    return jsonify(res)


@reports_bp.get("/top-risky-assets")
def top_risky_assets():
    # Rank assets by count of Fail with severity weighting
    severity_weight = {'Low': 1, 'Medium': 3, 'High': 6, 'Critical': 10}
    # Retrieve all and compute in Python for SQLite compatibility
    all_findings = db.session.query(Finding.asset_id, Finding.state, Finding.severity).all()
    score_map = {}
    for asset_id, state, sev in all_findings:
        if state != 'Fail':
            continue
        score_map.setdefault(asset_id, 0)
        score_map[asset_id] += severity_weight.get(sev, 3)
    assets = {a.id: a for a in Asset.query.filter(Asset.id.in_(score_map.keys())).all()}
    ranked = sorted(score_map.items(), key=lambda kv: kv[1], reverse=True)[:25]
    return jsonify([
        {
            'asset_id': aid,
            'asset_name': assets.get(aid).name if aid in assets else aid,
            'risk_score': score
        }
        for aid, score in ranked
    ])

