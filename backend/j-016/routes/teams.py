from flask import Blueprint, request, jsonify
from db import db
from models import Team

bp = Blueprint('teams', __name__)

@bp.route('/teams', methods=['POST'])
def create_team():
    data = request.get_json(force=True)
    name = data.get('name')
    if not name:
        return jsonify({'error': 'name is required'}), 400
    t = Team(
        name=name,
        timezone=data.get('timezone') or 'UTC',
        digest_enabled=bool(data.get('digest_enabled', True)),
        digest_frequency=data.get('digest_frequency') or 'hourly',
        digest_hour=data.get('digest_hour'),
        digest_minute=data.get('digest_minute', 0),
    )
    db.session.add(t)
    db.session.commit()
    return jsonify(t.to_dict()), 201

@bp.route('/teams', methods=['GET'])
def list_teams():
    teams = Team.query.order_by(Team.id.asc()).all()
    return jsonify([t.to_dict() for t in teams])

@bp.route('/teams/<int:team_id>', methods=['GET'])
def get_team(team_id: int):
    t = Team.query.get_or_404(team_id)
    return jsonify(t.to_dict())

@bp.route('/teams/<int:team_id>', methods=['PATCH'])
def update_team(team_id: int):
    t = Team.query.get_or_404(team_id)
    data = request.get_json(force=True)
    for field in ['name','timezone','digest_enabled','digest_frequency','digest_hour','digest_minute']:
        if field in data:
            setattr(t, field, data[field])
    db.session.add(t)
    db.session.commit()
    return jsonify(t.to_dict())

