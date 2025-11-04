from flask import Blueprint, request, jsonify, abort
from ..auth import require_team
from ..models import ProvisionTask, Environment

bp = Blueprint('tasks', __name__)


def _task_to_dict(t: ProvisionTask):
    return {
        'id': t.id,
        'environment_id': t.environment_id,
        'action': t.action,
        'status': t.status,
        'logs': t.logs or '',
        'created_at': t.created_at.isoformat() + 'Z',
        'updated_at': t.updated_at.isoformat() + 'Z'
    }


@bp.get('/tasks')
@require_team
def list_tasks():
    env_id = request.args.get('environment_id')
    q = ProvisionTask.query
    if env_id:
        env = Environment.query.get(env_id)
        if not env or env.team_id != request.team.id:
            abort(404, description='environment not found')
        q = q.filter_by(environment_id=env_id)
    else:
        # filter tasks to only those belonging to this team
        from sqlalchemy import exists
        q = q.filter(exists().where(Environment.id == ProvisionTask.environment_id).where(Environment.team_id == request.team.id))
    tasks = q.order_by(ProvisionTask.created_at.desc()).all()
    return jsonify([_task_to_dict(t) for t in tasks])


@bp.get('/tasks/<task_id>')
@require_team
def get_task(task_id):
    t = ProvisionTask.query.get(task_id)
    if not t:
        abort(404, description='task not found')
    env = Environment.query.get(t.environment_id)
    if not env or env.team_id != request.team.id:
        abort(404, description='task not found')
    return jsonify(_task_to_dict(t))

