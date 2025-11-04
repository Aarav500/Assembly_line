from flask import Blueprint, request, jsonify
from db import db
from models import Event, Team, Route
from services.routing import matches_filters
from services.delivery import queue_delivery

bp = Blueprint('events', __name__)

@bp.route('/events', methods=['POST'])
def ingest_event():
    data = request.get_json(force=True)
    team_id = data.get('team_id')
    if not team_id:
        return jsonify({'error': 'team_id is required'}), 400
    team = Team.query.get_or_404(team_id)

    ev = Event(
        team_id=team.id,
        title=data.get('title') or 'Untitled',
        message=data.get('message'),
        severity=data.get('severity') or 'info',
        event_type=data.get('event_type'),
        tags=data.get('tags') or [],
    )
    db.session.add(ev)
    db.session.commit()

    # Handle immediate routing
    routes = Route.query.filter_by(team_id=team.id, active=True, mode='immediate').all()
    matched_routes = []
    for r in routes:
        if matches_filters(ev.to_dict(), r.filters or {}):
            payload = {
                'title': ev.title,
                'message': ev.message,
                'severity': ev.severity,
                'event_type': ev.event_type,
                'tags': ev.tags or [],
                'event_id': ev.id,
                'team_id': team.id,
            }
            d = queue_delivery(team_id=team.id, route_id=r.id, channel=r.channel, target=r.target, payload=payload, delivery_type='single')
            matched_routes.append(d.id)

    return jsonify({'event': ev.to_dict(), 'deliveries_created': matched_routes}), 201

@bp.route('/teams/<int:team_id>/events', methods=['GET'])
def list_events(team_id: int):
    Team.query.get_or_404(team_id)
    limit = int(request.args.get('limit', '50'))
    after_id = request.args.get('after_id')
    q = Event.query.filter_by(team_id=team_id).order_by(Event.id.desc())
    if after_id:
        q = q.filter(Event.id < int(after_id))
    events = q.limit(limit).all()
    return jsonify([e.to_dict() for e in events])

