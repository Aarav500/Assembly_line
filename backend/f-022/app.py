import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import threading
import traceback
from datetime import datetime, timedelta
from secrets import token_urlsafe
from urllib.parse import urlencode

from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, flash

from db import init_db, create_action, update_action_status, update_action_result, get_action, list_actions, create_approval, get_approval, update_approval_status, list_pending_approvals, ensure_instance_dir
from playbooks import registry, match_playbook_for_alert, get_playbook_by_id

app = Flask(__name__)
app.config['DATABASE'] = os.environ.get('DB_PATH', os.path.join('instance', 'app.db'))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', 'changeme')

ensure_instance_dir()
init_db(app.config['DATABASE'])


def now_ts():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def approval_url(approval):
    base = url_for('approval_detail', approval_id=approval['id'], _external=True)
    return f"{base}?{urlencode({'token': approval['token']})}"


def validate_admin_or_link_token(approval, supplied_token: str | None) -> bool:
    if not supplied_token:
        return False
    if supplied_token == ADMIN_TOKEN:
        return True
    if approval and supplied_token == approval['token']:
        return True
    return False


def _log_and_append(logs, message):
    ts = now_ts()
    entry = f"[{ts}] {message}"
    logs.append(entry)
    app.logger.info(entry)


def run_action_async(action_id: int):
    t = threading.Thread(target=_run_action_worker, args=(action_id,), daemon=True)
    t.start()


def _run_action_worker(action_id: int):
    action = get_action(app.config['DATABASE'], action_id)
    if not action:
        app.logger.error(f"Action {action_id} not found")
        return
    playbook_id = action['playbook_id']
    playbook = get_playbook_by_id(playbook_id)
    if not playbook:
        update_action_status(app.config['DATABASE'], action_id, 'failed')
        update_action_result(app.config['DATABASE'], action_id, json.dumps({'error': f'Playbook {playbook_id} not found'}))
        return

    logs: list[str] = []
    try:
        update_action_status(app.config['DATABASE'], action_id, 'running')
        context = json.loads(action['context'] or '{}')
        _log_and_append(logs, f"Starting playbook '{playbook.name}' (id={playbook.id}) for alert '{action['alert_type']}'")
        result = playbook.execute(context, lambda msg: _log_and_append(logs, msg))
        outcome = {
            'playbook_id': playbook.id,
            'playbook_name': playbook.name,
            'context': context,
            'result': result,
            'logs': logs,
        }
        status = 'succeeded' if result.get('success') else 'failed'
        update_action_result(app.config['DATABASE'], action_id, json.dumps(outcome))
        update_action_status(app.config['DATABASE'], action_id, status)
        _log_and_append(logs, f"Playbook completed with status={status}")
    except Exception as e:
        _log_and_append(logs, f"Exception during playbook execution: {e}")
        _log_and_append(logs, traceback.format_exc())
        update_action_result(app.config['DATABASE'], action_id, json.dumps({'error': str(e), 'logs': logs}))
        update_action_status(app.config['DATABASE'], action_id, 'failed')


@app.route('/')
def index():
    actions = list_actions(app.config['DATABASE'], limit=10)
    pending = list_pending_approvals(app.config['DATABASE'])
    counts = {
        'total_actions': list_actions(app.config['DATABASE'], count_only=True),
        'pending_approvals': len(pending)
    }
    return render_template('index.html', actions=actions, pending=pending, counts=counts)


@app.route('/playbooks')
def playbooks_view():
    items = [
        {
            'id': pb.id,
            'name': pb.name,
            'description': pb.description,
            'risk': pb.risk,
            'auto_approve': pb.auto_approve,
            'mapped_alerts': pb.mapped_alerts,
        }
        for pb in registry.values()
    ]
    return render_template('playbooks.html', playbooks=items)


@app.route('/actions')
def actions_view():
    actions = list_actions(app.config['DATABASE'], limit=100)
    return render_template('actions.html', actions=actions)


@app.route('/actions/<int:action_id>')
def action_detail(action_id):
    action = get_action(app.config['DATABASE'], action_id)
    if not action:
        abort(404)
    result = None
    try:
        result = json.loads(action['result']) if action['result'] else None
    except Exception:
        result = {'raw': action['result']}
    return render_template('action_detail.html', action=action, result=result)


@app.route('/approvals')
def approvals_list():
    approvals = list_pending_approvals(app.config['DATABASE'])
    return render_template('approvals.html', approvals=approvals)


@app.route('/approvals/<int:approval_id>')
def approval_detail(approval_id):
    approval = get_approval(app.config['DATABASE'], approval_id)
    if not approval:
        abort(404)
    action = get_action(app.config['DATABASE'], approval['action_id'])
    if not action:
        abort(404)
    playbook = get_playbook_by_id(action['playbook_id'])
    token = request.args.get('token', '')
    return render_template('approval_detail.html', approval=approval, action=action, playbook=playbook, link_token=token)


@app.route('/approvals/<int:approval_id>/approve', methods=['POST'])
def approval_approve(approval_id):
    approval = get_approval(app.config['DATABASE'], approval_id)
    if not approval:
        abort(404)
    token = request.form.get('token') or request.headers.get('X-Admin-Token')
    if not validate_admin_or_link_token(approval, token):
        abort(403)
    if approval['status'] != 'pending':
        flash('Approval is not pending.', 'warning')
        return redirect(url_for('approval_detail', approval_id=approval_id))
    update_approval_status(app.config['DATABASE'], approval_id, 'approved')
    update_action_status(app.config['DATABASE'], approval['action_id'], 'approved')
    run_action_async(approval['action_id'])
    flash('Approval granted and playbook execution started.', 'success')
    return redirect(url_for('action_detail', action_id=approval['action_id']))


@app.route('/approvals/<int:approval_id>/deny', methods=['POST'])
def approval_deny(approval_id):
    approval = get_approval(app.config['DATABASE'], approval_id)
    if not approval:
        abort(404)
    token = request.form.get('token') or request.headers.get('X-Admin-Token')
    if not validate_admin_or_link_token(approval, token):
        abort(403)
    if approval['status'] != 'pending':
        flash('Approval is not pending.', 'warning')
        return redirect(url_for('approval_detail', approval_id=approval_id))
    update_approval_status(app.config['DATABASE'], approval_id, 'denied')
    update_action_status(app.config['DATABASE'], approval['action_id'], 'denied')
    flash('Approval denied.', 'info')
    return redirect(url_for('action_detail', action_id=approval['action_id']))


@app.route('/api/alerts', methods=['POST'])
def api_alerts():
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({'error': 'Invalid JSON'}), 400

    alert_type = payload.get('type')
    context = payload.get('context', {})
    if not alert_type:
        return jsonify({'error': 'Missing alert type'}), 400

    playbook = match_playbook_for_alert(alert_type)
    if not playbook:
        return jsonify({'error': f'No playbook mapped for alert type {alert_type}'}), 404

    action_id = create_action(
        app.config['DATABASE'],
        playbook_id=playbook.id,
        playbook_name=playbook.name,
        alert_type=alert_type,
        status='created',
        context=json.dumps(context)
    )

    if playbook.auto_approve:
        update_action_status(app.config['DATABASE'], action_id, 'queued')
        run_action_async(action_id)
        return jsonify({
            'action_id': action_id,
            'status': 'queued',
            'message': f"Playbook '{playbook.name}' started automatically",
        }), 202
    else:
        # Create approval request with TTL 60 minutes
        expires_at = (datetime.utcnow() + timedelta(minutes=60)).strftime('%Y-%m-%dT%H:%M:%SZ')
        approval_id = create_approval(
            app.config['DATABASE'],
            action_id=action_id,
            token=token_urlsafe(16),
            expires_at=expires_at
        )
        update_action_status(app.config['DATABASE'], action_id, 'awaiting_approval')
        approval = get_approval(app.config['DATABASE'], approval_id)
        return jsonify({
            'action_id': action_id,
            'status': 'awaiting_approval',
            'approval_id': approval_id,
            'approval_url': approval_url(approval),
            'message': f"Approval required for playbook '{playbook.name}'.",
        }), 202


@app.route('/api/actions/<int:action_id>')
def api_action_status(action_id):
    action = get_action(app.config['DATABASE'], action_id)
    if not action:
        return jsonify({'error': 'Not found'}), 404
    payload = dict(action)
    try:
        payload['context'] = json.loads(payload['context']) if payload.get('context') else None
    except Exception:
        pass
    try:
        payload['result'] = json.loads(payload['result']) if payload.get('result') else None
    except Exception:
        pass
    return jsonify(payload)


@app.route('/api/health')
def api_health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5000')), debug=True)



@app.route('/remediation/trigger', methods=['POST'])
def _auto_stub_remediation_trigger():
    return 'Auto-generated stub for /remediation/trigger', 200
