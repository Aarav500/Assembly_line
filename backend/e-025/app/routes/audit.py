from flask import Blueprint, request, jsonify
from ..auth import require_team
from ..models import AuditEvent

bp = Blueprint('audit', __name__)


def _audit_to_dict(a: AuditEvent):
    return {
        'id': a.id,
        'team_id': a.team_id,
        'environment_id': a.environment_id,
        'action': a.action,
        'actor': a.actor,
        'details': a.details,
        'created_at': a.created_at.isoformat() + 'Z'
    }


@bp.get('/audit')
@require_team
def list_audit():
    events = AuditEvent.query.filter_by(team_id=request.team.id).order_by(AuditEvent.created_at.desc()).limit(200).all()
    return jsonify([_audit_to_dict(e) for e in events])

