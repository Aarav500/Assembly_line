from flask import Blueprint, request, jsonify, abort
from sqlalchemy import and_
from ..auth import require_team
from ..db import db
from ..models import Environment, Team
from ..audit import log_event
from ..provisioner import provisioner, start_provision, start_deprovision

bp = Blueprint('environments', __name__)


def _env_to_dict(e: Environment):
    return {
        'id': e.id,
        'name': e.name,
        'type': e.env_type,
        'status': e.status,
        'region': e.region,
        'config': e.config,
        'team_id': e.team_id,
        'created_at': e.created_at.isoformat() + 'Z',
        'updated_at': e.updated_at.isoformat() + 'Z'
    }


def _active_statuses():
    return ['requested', 'provisioning', 'active']


def _check_quota(team: Team, env_type: str):
    limits = {
        'dev': team.quota_dev,
        'stage': team.quota_stage,
        'prod': team.quota_prod
    }
    limit = limits[env_type]
    count = Environment.query.filter(
        and_(Environment.team_id == team.id,
             Environment.env_type == env_type,
             Environment.status.in_(_active_statuses()))
    ).count()
    if count >= limit:
        abort(403, description=f'Quota exceeded for {env_type} (limit={limit})')


@bp.post('/environments')
@require_team
def create_environment():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    env_type = data.get('type')
    region = data.get('region')
    config = data.get('config') or {}
    auto_provision = bool(data.get('auto_provision', True))

    if not name or not env_type:
        abort(400, description='name and type are required')
    if env_type not in ('dev', 'stage', 'prod'):
        abort(400, description='type must be one of dev, stage, prod')

    _check_quota(request.team, env_type)

    env = Environment(name=name, env_type=env_type, region=region, team_id=request.team.id)
    env.config = config
    db.session.add(env)
    db.session.commit()

    log_event(team_id=request.team.id, action='environment_created', actor=request.team.name, environment_id=env.id, details={'name': name, 'type': env_type})

    if auto_provision:
        provisioner.submit(start_provision, env.id, request.team.name)

    return jsonify(_env_to_dict(env)), 201


@bp.get('/environments')
@require_team
def list_environments():
    env_type = request.args.get('type')
    status = request.args.get('status')
    q = Environment.query.filter_by(team_id=request.team.id)
    if env_type:
        q = q.filter_by(env_type=env_type)
    if status:
        q = q.filter_by(status=status)
    envs = q.order_by(Environment.created_at.desc()).all()
    return jsonify([_env_to_dict(e) for e in envs])


@bp.get('/environments/<env_id>')
@require_team
def get_environment(env_id):
    env = Environment.query.get(env_id)
    if not env or env.team_id != request.team.id:
        abort(404, description='environment not found')
    return jsonify(_env_to_dict(env))


@bp.patch('/environments/<env_id>')
@require_team
def update_environment(env_id):
    env = Environment.query.get(env_id)
    if not env or env.team_id != request.team.id:
        abort(404, description='environment not found')

    data = request.get_json(silent=True) or {}
    allowed_status_transitions = {
        'requested': ['provisioning', 'active', 'failed'],
        'provisioning': ['active', 'failed'],
        'active': ['failed'],
        'failed': [],
        'deprovisioning': [],
        'deleted': []
    }

    updated = False

    if 'name' in data:
        env.name = data['name']
        updated = True
    if 'region' in data:
        env.region = data['region']
        updated = True
    if 'config' in data and isinstance(data['config'], dict):
        cfg = env.config
        cfg.update(data['config'])
        env.config = cfg
        updated = True
    if 'status' in data:
        new_status = data['status']
        if new_status not in allowed_status_transitions.get(env.status, []):
            abort(400, description=f'illegal status transition from {env.status} to {new_status}')
        env.status = new_status
        updated = True

    if updated:
        db.session.commit()
        log_event(team_id=request.team.id, action='environment_updated', actor=request.team.name, environment_id=env.id, details={'changes': list(data.keys())})

    return jsonify(_env_to_dict(env))


@bp.delete('/environments/<env_id>')
@require_team
def delete_environment(env_id):
    env = Environment.query.get(env_id)
    if not env or env.team_id != request.team.id:
        abort(404, description='environment not found')
    if env.status in ('deleted', 'deprovisioning'):
        return jsonify({'message': 'already deleted or deprovisioning'}), 200

    provisioner.submit(start_deprovision, env.id, request.team.name)
    log_event(team_id=request.team.id, action='environment_delete_requested', actor=request.team.name, environment_id=env.id)
    return jsonify({'message': 'deprovision started', 'id': env.id})


@bp.post('/environments/<env_id>/provision')
@require_team
def provision_environment(env_id):
    env = Environment.query.get(env_id)
    if not env or env.team_id != request.team.id:
        abort(404, description='environment not found')

    if env.status in ('active', 'provisioning'):
        abort(409, description='environment already provisioned or in progress')

    _check_quota(request.team, env.env_type)

    provisioner.submit(start_provision, env.id, request.team.name)
    log_event(team_id=request.team.id, action='provision_requested', actor=request.team.name, environment_id=env.id)
    return jsonify({'message': 'provision started', 'id': env.id})


@bp.post('/environments/<env_id>/deprovision')
@require_team
def deprovision_environment(env_id):
    env = Environment.query.get(env_id)
    if not env or env.team_id != request.team.id:
        abort(404, description='environment not found')
    if env.status in ('deleted', 'deprovisioning'):
        abort(409, description='already deprovisioned or in progress')

    provisioner.submit(start_deprovision, env.id, request.team.name)
    log_event(team_id=request.team.id, action='deprovision_requested', actor=request.team.name, environment_id=env.id)
    return jsonify({'message': 'deprovision started', 'id': env.id})


@bp.get('/quotas')
@require_team
def quotas():
    t = request.team
    usage = {}
    for k in ('dev', 'stage', 'prod'):
        usage[k] = Environment.query.filter_by(team_id=t.id, env_type=k).filter(Environment.status.in_(['requested','provisioning','active'])).count()
    return jsonify({
        'limits': {'dev': t.quota_dev, 'stage': t.quota_stage, 'prod': t.quota_prod},
        'usage': usage
    })

