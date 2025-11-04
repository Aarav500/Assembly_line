from flask import Blueprint, request, jsonify
from db import db
from models import Route, Team

bp = Blueprint('routes', __name__)

@bp.route('/teams/<int:team_id>/routes', methods=['POST'])
def create_route(team_id: int):
    team = Team.query.get_or_404(team_id)
    data = request.get_json(force=True)
    channel = data.get('channel')
    target = data.get('target')
    if channel not in ['email','slack','webhook']:
        return jsonify({'error': 'invalid channel'}), 400
    if not target:
        return jsonify({'error': 'target is required'}), 400
    mode = data.get('mode') or 'immediate'
    if mode not in ['immediate','digest']:
        return jsonify({'error': 'invalid mode'}), 400
    r = Route(
        team_id=team.id,
        channel=channel,
        target=target,
        mode=mode,
        filters=data.get('filters') or {},
        active=bool(data.get('active', True))
    )
    db.session.add(r)
    db.session.commit()
    return jsonify(r.to_dict()), 201

@bp.route('/teams/<int:team_id>/routes', methods=['GET'])
def list_routes(team_id: int):
    Team.query.get_or_404(team_id)
    routes = Route.query.filter_by(team_id=team_id).order_by(Route.id.asc()).all()
    return jsonify([r.to_dict() for r in routes])

@bp.route('/routes/<int:route_id>', methods=['PATCH'])
def update_route(route_id: int):
    r = Route.query.get_or_404(route_id)
    data = request.get_json(force=True)
    for field in ['channel','target','mode','filters','active']:
        if field in data:
            setattr(r, field, data[field])
    db.session.add(r)
    db.session.commit()
    return jsonify(r.to_dict())

@bp.route('/routes/<int:route_id>', methods=['DELETE'])
def delete_route(route_id: int):
    r = Route.query.get_or_404(route_id)
    db.session.delete(r)
    db.session.commit()
    return jsonify({'deleted': True})

