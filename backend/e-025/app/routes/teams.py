from flask import Blueprint, request, jsonify, abort
from ..auth import require_admin, require_team, generate_api_key
from ..db import db
from ..models import Team
from ..config import Config

bp = Blueprint('teams', __name__)


@bp.post('/admin/teams')
@require_admin
def create_team():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    if not name:
        abort(400, description='name is required')
    if Team.query.filter_by(name=name).first():
        abort(409, description='team name already exists')
    api_key = generate_api_key()
    quota_dev = int(data.get('quota_dev', Config.DEFAULT_QUOTA_DEV))
    quota_stage = int(data.get('quota_stage', Config.DEFAULT_QUOTA_STAGE))
    quota_prod = int(data.get('quota_prod', Config.DEFAULT_QUOTA_PROD))

    team = Team(name=name, api_key=api_key, quota_dev=quota_dev, quota_stage=quota_stage, quota_prod=quota_prod)
    db.session.add(team)
    db.session.commit()

    return jsonify({
        'id': team.id,
        'name': team.name,
        'api_key': team.api_key,
        'quotas': {
            'dev': team.quota_dev, 'stage': team.quota_stage, 'prod': team.quota_prod
        },
        'created_at': team.created_at.isoformat() + 'Z'
    }), 201


@bp.get('/admin/teams')
@require_admin
def list_teams():
    teams = Team.query.order_by(Team.created_at.desc()).all()
    return jsonify([
        {
            'id': t.id,
            'name': t.name,
            'api_key': t.api_key,
            'quotas': {'dev': t.quota_dev, 'stage': t.quota_stage, 'prod': t.quota_prod},
            'created_at': t.created_at.isoformat() + 'Z'
        } for t in teams
    ])


@bp.get('/admin/teams/<team_id>')
@require_admin
def get_team(team_id):
    t = Team.query.get(team_id)
    if not t:
        abort(404, description='team not found')
    return jsonify({
        'id': t.id,
        'name': t.name,
        'api_key': t.api_key,
        'quotas': {'dev': t.quota_dev, 'stage': t.quota_stage, 'prod': t.quota_prod},
        'created_at': t.created_at.isoformat() + 'Z'
    })


@bp.post('/admin/teams/<team_id>/rotate-key')
@require_admin
def rotate_team_key(team_id):
    t = Team.query.get(team_id)
    if not t:
        abort(404, description='team not found')
    t.api_key = generate_api_key()
    db.session.commit()
    return jsonify({'id': t.id, 'api_key': t.api_key})


@bp.get('/me')
@require_team
def me():
    t = request.team
    return jsonify({
        'id': t.id,
        'name': t.name,
        'quotas': {'dev': t.quota_dev, 'stage': t.quota_stage, 'prod': t.quota_prod},
        'created_at': t.created_at.isoformat() + 'Z'
    })

