import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
from flask import Flask, request, jsonify, send_file
from werkzeug.exceptions import BadRequest

from config import AppConfig
import db
import storage
import retention
import evidence

app = Flask(__name__)

# Ensure data directories and DB are ready
os.makedirs(AppConfig.DATA_DIR, exist_ok=True)
os.makedirs(AppConfig.BACKUP_DIR, exist_ok=True)
os.makedirs(AppConfig.EVIDENCE_DIR, exist_ok=True)

db.init_db(AppConfig.DB_PATH)


def get_active_policy():
    p = db.get_policy(AppConfig.DB_PATH)
    if not p:
        # create default
        db.save_policy(AppConfig.DB_PATH, AppConfig.default_policy())
        p = db.get_policy(AppConfig.DB_PATH)
    return p


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'app': 'backup-retention-compliance-automation-and-evidence-packaging',
        'data_dir': AppConfig.DATA_DIR,
        'backup_dir': AppConfig.BACKUP_DIR,
        'evidence_dir': AppConfig.EVIDENCE_DIR
    })


@app.route('/backups', methods=['GET'])
def list_backups():
    backups = storage.list_backups(AppConfig.BACKUP_DIR)
    return jsonify({'backups': backups, 'count': len(backups)})


@app.route('/backups/simulate', methods=['POST'])
def simulate_backup():
    body = request.get_json(silent=True) or {}
    size_kb = int(body.get('size_kb', 16))
    label = body.get('label')
    created = storage.create_dummy_backup(AppConfig.BACKUP_DIR, size_kb=size_kb, label=label)
    return jsonify({'created': created})


@app.route('/policies', methods=['GET'])
def get_policy():
    p = get_active_policy()
    return jsonify({'policy': p})


@app.route('/policies', methods=['POST'])
def update_policy():
    body = request.get_json(silent=True)
    if not body or 'policy' not in body:
        raise BadRequest('Missing policy in request body')
    current = get_active_policy()
    updated = {**current, **body['policy']}
    # sanitize
    for k in list(updated.keys()):
        if k not in {'retain_days', 'min_backups', 'max_backups', 'require_frequency_hours', 'backup_dir'}:
            updated.pop(k, None)
    if updated.get('backup_dir'):
        # override config if provided
        AppConfig.BACKUP_DIR = updated['backup_dir']
        os.makedirs(AppConfig.BACKUP_DIR, exist_ok=True)
    # constraints
    if updated.get('max_backups') is not None and updated.get('min_backups') is not None:
        if int(updated['max_backups']) < int(updated['min_backups']):
            raise BadRequest('max_backups cannot be less than min_backups')
    db.save_policy(AppConfig.DB_PATH, updated)
    return jsonify({'policy': updated})


@app.route('/compliance/check', methods=['POST'])
def compliance_check():
    policy = get_active_policy()
    backups = storage.list_backups(AppConfig.BACKUP_DIR)
    result = retention.check_compliance(policy, backups)
    return jsonify({'policy': policy, 'result': result})


@app.route('/compliance/enforce', methods=['POST'])
def compliance_enforce():
    # optional dry_run flag in body
    body = request.get_json(silent=True) or {}
    dry_run = bool(body.get('dry_run', False))
    note = body.get('note')

    policy = get_active_policy()
    before = storage.list_backups(AppConfig.BACKUP_DIR)
    check = retention.check_compliance(policy, before)

    to_delete = check.get('deletion_candidates', [])
    actions = []

    if not dry_run:
        for item in to_delete:
            try:
                storage.delete_backup(item['path'], base_dir=AppConfig.BACKUP_DIR)
                actions.append({'action': 'delete', 'target': item['name'], 'path': item['path'], 'status': 'success'})
            except Exception as e:
                actions.append({'action': 'delete', 'target': item['name'], 'path': item['path'], 'status': 'error', 'error': str(e)})

    after = storage.list_backups(AppConfig.BACKUP_DIR)

    event_id = str(uuid.uuid4())
    pkg = evidence.generate_evidence_package(
        evidence_dir=AppConfig.EVIDENCE_DIR,
        event_id=event_id,
        policy=policy,
        before_backups=before,
        after_backups=after,
        actions=actions,
        compliance_result=check,
        note=note or ('dry-run' if dry_run else 'enforce')
    )

    event_record = {
        'id': event_id,
        'created_at': pkg['created_at'],
        'summary': pkg['summary'],
        'details': pkg['manifest'],
        'zip_path': pkg['zip_path']
    }
    db.add_event(AppConfig.DB_PATH, event_record)

    return jsonify({
        'event_id': event_id,
        'dry_run': dry_run,
        'actions': actions,
        'before_count': len(before),
        'after_count': len(after),
        'evidence': {
            'zip_path': pkg['zip_path'],
            'download_url': f"/evidence/{event_id}/download",
            'manifest_hash': pkg['manifest_hash']
        },
        'compliance_result': check
    })


@app.route('/evidence/package', methods=['POST'])
def package_evidence():
    body = request.get_json(silent=True) or {}
    note = body.get('note', 'ad-hoc-package')
    policy = get_active_policy()
    backups = storage.list_backups(AppConfig.BACKUP_DIR)
    check = retention.check_compliance(policy, backups)
    event_id = str(uuid.uuid4())

    pkg = evidence.generate_evidence_package(
        evidence_dir=AppConfig.EVIDENCE_DIR,
        event_id=event_id,
        policy=policy,
        before_backups=backups,
        after_backups=backups,
        actions=[],
        compliance_result=check,
        note=note
    )

    event_record = {
        'id': event_id,
        'created_at': pkg['created_at'],
        'summary': pkg['summary'],
        'details': pkg['manifest'],
        'zip_path': pkg['zip_path']
    }
    db.add_event(AppConfig.DB_PATH, event_record)

    return jsonify({
        'event_id': event_id,
        'evidence': {
            'zip_path': pkg['zip_path'],
            'download_url': f"/evidence/{event_id}/download",
            'manifest_hash': pkg['manifest_hash']
        }
    })


@app.route('/evidence/<event_id>/download', methods=['GET'])
def download_evidence(event_id):
    event = db.get_event(AppConfig.DB_PATH, event_id)
    if not event:
        raise BadRequest('Unknown event id')
    path = event['zip_path']
    if not os.path.isfile(path):
        raise BadRequest('Evidence package not found on disk')
    return send_file(path, as_attachment=True)


@app.route('/compliance/history', methods=['GET'])
def history():
    limit = int(request.args.get('limit', 50))
    events = db.list_events(AppConfig.DB_PATH, limit)
    return jsonify({'events': events})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '8000'))) 



def create_app():
    return app


@app.route('/backups/compliance', methods=['GET'])
def _auto_stub_backups_compliance():
    return 'Auto-generated stub for /backups/compliance', 200
