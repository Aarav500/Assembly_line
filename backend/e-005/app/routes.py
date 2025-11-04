from flask import Blueprint, current_app, jsonify, request
from .auth import require_token
from .models import db, Policy, DeletionLog
from .registry import RegistryClient
from .policy_engine import PolicyEngine

api_bp = Blueprint('api', __name__)


def get_registry_client():
    cfg = current_app.config
    return RegistryClient(
        base_url=cfg['REGISTRY_URL'],
        username=cfg.get('REGISTRY_USERNAME'),
        password=cfg.get('REGISTRY_PASSWORD'),
        verify_ssl=cfg.get('REGISTRY_VERIFY_SSL', True),
    )


@api_bp.route('/registry/ping', methods=['GET'])
@require_token
def registry_ping():
    client = get_registry_client()
    return jsonify({'ok': client.ping()})


@api_bp.route('/registry/repositories', methods=['GET'])
@require_token
def list_repositories():
    pattern = request.args.get('pattern')
    client = get_registry_client()
    repos = client.list_repositories()
    if pattern:
        from .utils import glob_match
        repos = [r for r in repos if glob_match(pattern, r)]
    return jsonify({'repositories': repos})


@api_bp.route('/registry/repositories/<path:repository>/tags', methods=['GET'])
@require_token
def list_tags(repository):
    client = get_registry_client()
    tags = client.list_tags(repository)
    enrich = request.args.get('enrich', 'false').lower() == 'true'
    if not enrich:
        return jsonify({'repository': repository, 'tags': tags})
    details = []
    for t in tags:
        try:
            details.append(client.tag_metadata(repository, t))
        except Exception:
            details.append({'tag': t})
    return jsonify({'repository': repository, 'tags': details})


@api_bp.route('/policies', methods=['GET'])
@require_token
def get_policies():
    policies = Policy.query.order_by(Policy.id.asc()).all()
    return jsonify({'policies': [p.to_dict() for p in policies]})


@api_bp.route('/policies/<int:policy_id>', methods=['GET'])
@require_token
def get_policy(policy_id):
    p = Policy.query.get_or_404(policy_id)
    return jsonify(p.to_dict())


@api_bp.route('/policies', methods=['POST'])
@require_token
def create_policy():
    data = request.get_json(force=True)
    cfg = current_app.config
    p = Policy(
        name=data['name'],
        repository_pattern=data['repository_pattern'],
        keep_last=data.get('keep_last'),
        max_age_days=data.get('max_age_days'),
        keep_tags_regex=data.get('keep_tags_regex'),
        exclude_tags_regex=data.get('exclude_tags_regex'),
        protected_tags=data.get('protected_tags'),
        dry_run=data.get('dry_run', cfg.get('DRY_RUN_DEFAULT', True)),
        enabled=data.get('enabled', True),
        notes=data.get('notes'),
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


@api_bp.route('/policies/<int:policy_id>', methods=['PUT'])
@require_token
def update_policy(policy_id):
    data = request.get_json(force=True)
    p = Policy.query.get_or_404(policy_id)
    for field in ['name','repository_pattern','keep_last','max_age_days','keep_tags_regex','exclude_tags_regex','protected_tags','dry_run','enabled','notes']:
        if field in data:
            setattr(p, field, data[field])
    db.session.commit()
    return jsonify(p.to_dict())


@api_bp.route('/policies/<int:policy_id>', methods=['DELETE'])
@require_token
def delete_policy(policy_id):
    p = Policy.query.get_or_404(policy_id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'deleted': True})


@api_bp.route('/policies/<int:policy_id>/preview', methods=['POST'])
@require_token
def preview_policy(policy_id):
    p = Policy.query.get_or_404(policy_id)
    client = get_registry_client()
    engine = PolicyEngine(client)
    summary = engine.evaluate_policy(p)
    return jsonify(summary)


@api_bp.route('/policies/<int:policy_id>/apply', methods=['POST'])
@require_token
def apply_policy(policy_id):
    body = request.get_json(silent=True) or {}
    simulate = body.get('simulate')
    p = Policy.query.get_or_404(policy_id)
    client = get_registry_client()
    engine = PolicyEngine(client)
    summary = engine.apply_policy(p, simulate=simulate)
    return jsonify(summary)


@api_bp.route('/logs', methods=['GET'])
@require_token
def list_logs():
    q = DeletionLog.query.order_by(DeletionLog.id.desc())
    policy_id = request.args.get('policy_id')
    if policy_id:
        q = q.filter(DeletionLog.policy_id == int(policy_id))
    repo = request.args.get('repository')
    if repo:
        q = q.filter(DeletionLog.repository == repo)
    limit = int(request.args.get('limit', '100'))
    logs = q.limit(limit).all()
    return jsonify({'logs': [l.to_dict() for l in logs]})

