from flask import Blueprint, request, jsonify
from datetime import datetime

from .models import db, Owner, OwnershipRule, TestCase, TestRun, RetestJob
from .services import record_test_run, analyze_all_tests_and_schedule, execute_pending_retests, refresh_assignments_for_all_tests

api_bp = Blueprint('api', __name__)


def parse_datetime(dt_str):
    if not dt_str:
        return None
    try:
        # Accepts 'YYYY-MM-DDTHH:MM:SS' optionally with microseconds and Z
        s = dt_str.rstrip('Z')
        return datetime.fromisoformat(s)
    except Exception:
        return None


@api_bp.route('/owners', methods=['POST'])
def create_owner():
    payload = request.get_json(force=True)
    name = payload.get('name')
    email = payload.get('email')
    if not name or not email:
        return jsonify({'error': 'name and email are required'}), 400
    if Owner.query.filter_by(name=name).first():
        return jsonify({'error': 'owner with this name already exists'}), 409
    owner = Owner(name=name, email=email)
    db.session.add(owner)
    db.session.commit()
    return jsonify(owner.to_dict()), 201


@api_bp.route('/ownership-rules', methods=['POST'])
def create_rule():
    payload = request.get_json(force=True)
    pattern = payload.get('pattern')
    scope = payload.get('scope', 'path')
    priority = int(payload.get('priority', 100))
    owner_id = payload.get('owner_id')

    if not pattern or not owner_id:
        return jsonify({'error': 'pattern and owner_id are required'}), 400

    owner = Owner.query.get(owner_id)
    if not owner:
        return jsonify({'error': 'owner not found'}), 404

    if scope not in ['path', 'name']:
        return jsonify({'error': "scope must be 'path' or 'name'"}), 400

    rule = OwnershipRule(pattern=pattern, scope=scope, priority=priority, owner_id=owner_id)
    db.session.add(rule)
    db.session.commit()
    return jsonify(rule.to_dict()), 201


@api_bp.route('/testruns', methods=['POST'])
def create_test_run():
    payload = request.get_json(force=True)
    name = payload.get('test_name') or payload.get('name')
    path = payload.get('path')
    status = payload.get('status')
    duration_ms = payload.get('duration_ms')
    build_id = payload.get('build_id')
    commit_sha = payload.get('commit_sha')
    executed_at = parse_datetime(payload.get('executed_at'))

    if not name or not status:
        return jsonify({'error': 'test_name and status are required'}), 400

    try:
        run = record_test_run(name=name, path=path, status=status, duration_ms=duration_ms, build_id=build_id, commit_sha=commit_sha, executed_at=executed_at)
        return jsonify(run.to_dict()), 201
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400


@api_bp.route('/tests', methods=['GET'])
def list_tests():
    tests = TestCase.query.order_by(TestCase.name.asc()).all()
    return jsonify([t.to_dict() for t in tests])


@api_bp.route('/tests/<int:test_id>', methods=['GET'])
def get_test(test_id):
    t = TestCase.query.get(test_id)
    if not t:
        return jsonify({'error': 'not found'}), 404
    return jsonify(t.to_dict())


@api_bp.route('/retests', methods=['GET'])
def list_retests():
    jobs = RetestJob.query.order_by(RetestJob.scheduled_at.desc()).limit(200).all()
    return jsonify([j.to_dict() for j in jobs])


@api_bp.route('/retests/execute', methods=['POST'])
def execute_retests():
    payload = request.get_json(silent=True) or {}
    limit = int(payload.get('limit', 5))
    jobs = execute_pending_retests(limit=limit)
    return jsonify([j.to_dict() for j in jobs])


@api_bp.route('/analyze', methods=['POST'])
def analyze_now():
    jobs = analyze_all_tests_and_schedule()
    return jsonify({'scheduled': [j.to_dict() for j in jobs], 'count': len(jobs)})


@api_bp.route('/assignments/refresh', methods=['POST'])
def refresh_assignments():
    count = refresh_assignments_for_all_tests()
    return jsonify({'updated_assignments': count})


@api_bp.route('/owners', methods=['GET'])
def list_owners():
    owners = Owner.query.order_by(Owner.name.asc()).all()
    return jsonify([o.to_dict() for o in owners])


@api_bp.route('/ownership-rules', methods=['GET'])
def list_rules():
    rules = OwnershipRule.query.order_by(OwnershipRule.priority.asc(), OwnershipRule.created_at.asc()).all()
    return jsonify([r.to_dict() for r in rules])

