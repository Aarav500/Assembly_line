from flask import Blueprint, request, jsonify
from ..db import db
from ..models import Rule

rules_bp = Blueprint('rules', __name__)


@rules_bp.get("")
def list_rules():
    q = Rule.query
    service = request.args.get('service')
    if service:
        q = q.filter(Rule.service == service)
    severity = request.args.get('severity')
    if severity:
        q = q.filter(Rule.severity == severity)
    return jsonify([r.to_dict() for r in q.order_by(Rule.key.asc()).all()])


@rules_bp.post("")
def create_rule():
    data = request.get_json(force=True)
    required = ['key', 'title', 'severity']
    for r in required:
        if r not in data:
            return jsonify({'error': f'missing_field:{r}'}), 400
    if Rule.query.filter_by(key=data['key']).first():
        return jsonify({'error': 'rule_key_exists'}), 409
    rule = Rule(
        key=data['key'],
        title=data['title'],
        severity=data['severity'],
        description=data.get('description'),
        remediation_guidance=data.get('remediation_guidance'),
        service=data.get('service'),
        query=data.get('query')
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify(rule.to_dict()), 201


@rules_bp.get("/<rule_id>")
def get_rule(rule_id):
    rule = Rule.query.get_or_404(rule_id)
    return jsonify(rule.to_dict())

