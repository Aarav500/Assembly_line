import os
from flask import Blueprint, jsonify, request, current_app, abort
from typing import Any, Dict, Optional

from config import Config
from models.incidents import create_incident, get_incident, list_incidents, add_action, get_action
from playbooks.containment import ContainmentPlaybook
from services.isolation import get_isolation_provider
from services.key_revocation import get_key_revocation_provider
from utils.audit import list_audit, log_audit

api_bp = Blueprint('api', __name__, url_prefix='/api')


def require_api_key():
    expected = Config.API_KEY
    if not expected:
        return
    provided = request.headers.get('X-API-Key')
    if provided != expected:
        abort(401, description='Unauthorized')


@api_bp.before_request
def _auth():
    require_api_key()


@api_bp.route('/incidents', methods=['POST'])
def api_create_incident():
    data = request.get_json(force=True, silent=True) or {}
    title = data.get('title') or 'Incident'
    severity = data.get('severity') or 'medium'
    incident_data = data.get('data') or {}
    auto_contain = bool(data.get('auto_contain', False))
    assets = data.get('assets') or []
    keys = data.get('keys') or []
    dry_run = data.get('dry_run')

    inc = create_incident(title=title, severity=severity, data=incident_data)

    task_info: Optional[Dict[str, Any]] = None
    if auto_contain:
        task_id = current_app.task_runner.submit(_run_containment_task, inc['id'], assets, keys, dry_run, data.get('reason'))
        task_info = {'task_id': task_id}

    return jsonify({'incident': inc, 'task': task_info}), 201


@api_bp.route('/incidents', methods=['GET'])
def api_list_incidents():
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    return jsonify({'incidents': list_incidents(limit, offset)})


@api_bp.route('/incidents/<incident_id>', methods=['GET'])
def api_get_incident(incident_id: str):
    inc = get_incident(incident_id)
    if not inc:
        abort(404, description='Incident not found')
    return jsonify({'incident': inc})


@api_bp.route('/incidents/<incident_id>/playbooks/containment', methods=['POST'])
def api_run_containment(incident_id: str):
    data = request.get_json(force=True, silent=True) or {}
    assets = data.get('assets') or []
    keys = data.get('keys') or []
    dry_run = data.get('dry_run')
    reason = data.get('reason')
    async_run = bool(data.get('async', True))

    if async_run:
        task_id = current_app.task_runner.submit(_run_containment_task, incident_id, assets, keys, dry_run, reason)
        return jsonify({'task_id': task_id}), 202
    else:
        res = _run_containment_task(incident_id, assets, keys, dry_run, reason)
        return jsonify({'result': res})


@api_bp.route('/actions/isolate', methods=['POST'])
def api_isolate_action():
    data = request.get_json(force=True, silent=True) or {}
    asset_id = data.get('asset_id')
    reason = data.get('reason')
    incident_id = data.get('incident_id')
    dry_run = data.get('dry_run')

    if not asset_id:
        abort(400, description='asset_id is required')

    provider = get_isolation_provider(Config.ISOLATION_PROVIDER)
    action_id = add_action(incident_id, 'isolate', 'running', {'asset_id': asset_id})

    try:
        if dry_run or Config.DEFAULT_DRY_RUN:
            res = {'asset_id': asset_id, 'provider': provider.name, 'status': 'dry_run', 'details': 'No action taken'}
        else:
            res = provider.isolate(asset_id=asset_id, reason=reason, incident_id=incident_id)
        log_audit(actor='api', action='isolate', target=asset_id, status='success', detail='on-demand isolate')
        from models.incidents import update_action as _upd
        _upd(action_id, status='completed', result=res)
        return jsonify({'result': res}), 200
    except Exception as e:
        from models.incidents import update_action as _upd
        _upd(action_id, status='failed', result={'error': str(e)})
        abort(500, description=str(e))


@api_bp.route('/actions/revoke-key', methods=['POST'])
def api_revoke_key_action():
    data = request.get_json(force=True, silent=True) or {}
    key_id = data.get('key_id')
    user = data.get('user')
    reason = data.get('reason')
    incident_id = data.get('incident_id')
    dry_run = data.get('dry_run')

    if not key_id:
        abort(400, description='key_id is required')

    provider = get_key_revocation_provider(Config.KEY_REVOCATION_PROVIDER)
    action_id = add_action(incident_id, 'revoke_key', 'running', {'key_id': key_id, 'user': user})

    try:
        if dry_run or Config.DEFAULT_DRY_RUN:
            res = {'key_id': key_id, 'user': user, 'provider': provider.name, 'status': 'dry_run', 'details': 'No action taken'}
        else:
            res = provider.revoke_key(key_id=key_id, user=user, reason=reason, incident_id=incident_id)
        log_audit(actor='api', action='revoke_key', target=f'key:{key_id}', status='success', detail='on-demand revoke')
        from models.incidents import update_action as _upd
        _upd(action_id, status='completed', result=res)
        return jsonify({'result': res}), 200
    except Exception as e:
        from models.incidents import update_action as _upd
        _upd(action_id, status='failed', result={'error': str(e)})
        abort(500, description=str(e))


@api_bp.route('/tasks/<task_id>', methods=['GET'])
def api_get_task(task_id: str):
    task = current_app.task_runner.get(task_id)
    if not task:
        abort(404, description='Task not found')
    return jsonify(task)


@api_bp.route('/audit', methods=['GET'])
def api_list_audit():
    limit = int(request.args.get('limit', 200))
    offset = int(request.args.get('offset', 0))
    return jsonify({'audit': list_audit(limit, offset)})


# Internal task function

def _run_containment_task(incident_id: str, assets, keys, dry_run=None, reason: Optional[str] = None) -> Dict[str, Any]:
    pb = ContainmentPlaybook(incident_id, dry_run=dry_run)
    return pb.run(assets=assets, keys=keys, reason=reason)

