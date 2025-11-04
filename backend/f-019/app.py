import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import os
import time
from datetime import datetime
from flask import Flask, request, jsonify

from config import (
    LOCAL_DESIRED_PATH,
    DATA_DIR,
    DEFAULT_MODE,
    GITHUB_REPO,
    GITHUB_BASE_BRANCH,
)
from services.drift import load_desired_state, compute_drift, save_last_drift, load_last_drift, apply_drift_to_desired
from services.remediation import build_remediation_suggestions
from services.alerts import send_alert
from services.github_client import GitHubClient

app = Flask(__name__)


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


@app.route('/api/v1/drift/check', methods=['POST'])
def drift_check():
    ensure_data_dir()
    payload = request.get_json(force=True, silent=True) or {}
    mode = payload.get('mode', DEFAULT_MODE)

    # Load actual state from payload or fallback to data file
    actual_state = payload.get('actual_state')
    if actual_state is None:
        actual_path = os.path.join(DATA_DIR, 'actual_state.json')
        if os.path.exists(actual_path):
            with open(actual_path, 'r') as f:
                actual_state = json.load(f)
        else:
            return jsonify({
                'error': 'No actual_state provided and no cached actual_state found.'
            }), 400
    else:
        # Cache the provided actual_state
        with open(os.path.join(DATA_DIR, 'actual_state.json'), 'w') as f:
            json.dump(actual_state, f, indent=2)

    # Load desired state
    desired_state, desired_source = load_desired_state()

    diffs = compute_drift(desired_state, actual_state)

    summary = {
        'total_drift_items': len(diffs),
        'by_type': {
            'missing_in_actual': sum(1 for d in diffs if d['kind'] == 'missing_in_actual'),
            'extra_in_actual': sum(1 for d in diffs if d['kind'] == 'extra_in_actual'),
            'attribute_diff': sum(1 for d in diffs if d['kind'] == 'attribute_diff')
        },
        'mode': mode,
        'desired_source': desired_source
    }

    result = {
        'summary': summary,
        'diffs': diffs,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }

    save_last_drift(result)

    if len(diffs) > 0:
        send_alert(f"Environment drift detected: {summary['total_drift_items']} item(s) differ.")

    return jsonify(result)


@app.route('/api/v1/drift/status', methods=['GET'])
def drift_status():
    ensure_data_dir()
    last = load_last_drift()
    if not last:
        return jsonify({'message': 'No drift run recorded yet.'}), 404
    return jsonify(last)


@app.route('/api/v1/drift/suggest', methods=['POST'])
def drift_suggest():
    ensure_data_dir()
    payload = request.get_json(force=True, silent=True) or {}

    # Use provided or last drift
    diffs = payload.get('diffs')
    desired_state = None
    actual_state = None
    mode = payload.get('mode', DEFAULT_MODE)

    if diffs is None:
        last = load_last_drift()
        if not last:
            return jsonify({'error': 'No diffs provided and no previous drift results found.'}), 400
        diffs = last.get('diffs', [])
        # Load desired and actual for better suggestions
        desired_state, _ = load_desired_state()
        actual_path = os.path.join(DATA_DIR, 'actual_state.json')
        if os.path.exists(actual_path):
            with open(actual_path, 'r') as f:
                actual_state = json.load(f)
    else:
        desired_state, _ = load_desired_state()
        actual_state = payload.get('actual_state')

    suggestions = build_remediation_suggestions(diffs, desired_state, actual_state, mode)

    return jsonify({
        'mode': mode,
        'suggestions': suggestions,
        'count': len(suggestions)
    })


@app.route('/api/v1/drift/pr', methods=['POST'])
def drift_pr():
    ensure_data_dir()
    payload = request.get_json(force=True, silent=True) or {}
    mode = payload.get('mode', 'update_desired')

    if GITHUB_REPO is None:
        return jsonify({'error': 'GITHUB_REPO not configured. Cannot open PR.'}), 400

    if mode != 'update_desired':
        return jsonify({'error': "PR generation currently supports only mode='update_desired' (align desired to actual)."}), 400

    # Acquire desired and actual
    desired_state, desired_source = load_desired_state()
    actual_state = payload.get('actual_state')
    if actual_state is None:
        actual_path = os.path.join(DATA_DIR, 'actual_state.json')
        if os.path.exists(actual_path):
            with open(actual_path, 'r') as f:
                actual_state = json.load(f)
        else:
            return jsonify({'error': 'No actual_state provided and none cached. Cannot build PR.'}), 400

    diffs = payload.get('diffs')
    if diffs is None:
        diffs = compute_drift(desired_state, actual_state)

    if len(diffs) == 0:
        return jsonify({'message': 'No drift detected. Nothing to open a PR for.'}), 200

    # Build new desired state that matches actual
    new_desired = apply_drift_to_desired(desired_state, actual_state, diffs)

    # Prepare PR metadata
    title = payload.get('title') or f"Align desired to actual: {len(diffs)} drift item(s)"
    body = payload.get('body') or (
        f"This PR updates the desired state to reflect the current environment.\n\n"
        f"Drift items: {len(diffs)}\n\n"
        f"Generated at {datetime.utcnow().isoformat()}Z"
    )

    branch_suffix = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    new_branch = payload.get('branch') or f"drift-fix-{branch_suffix}"

    # Serialize desired content
    new_content = json.dumps(new_desired, indent=2) + "\n"

    # Push changes and open PR
    gh = GitHubClient()

    try:
        gh.ensure_branch_from_base(new_branch, GITHUB_BASE_BRANCH)
        gh.create_or_update_file(
            path=gh.desired_path(),
            content=new_content,
            message=title,
            branch=new_branch
        )
        pr = gh.create_pull_request(title=title, body=body, head=new_branch, base=GITHUB_BASE_BRANCH)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({
        'message': 'PR created',
        'pr_url': pr.get('html_url'),
        'branch': new_branch,
        'repo': GITHUB_REPO,
        'updated_file': gh.desired_path(),
        'diffs_count': len(diffs)
    })


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'time': time.time()})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '8080')))



def create_app():
    return app


@app.route('/api/drift/detect', methods=['POST'])
def _auto_stub_api_drift_detect():
    return 'Auto-generated stub for /api/drift/detect', 200
