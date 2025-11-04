import datetime
from flask import Blueprint, request, jsonify

from .upgrade_generator import (
    generate_upgrade_notes,
    parse_commits_from_git,
)

bp = Blueprint('upgrade_generator', __name__)


@bp.route('/generate', methods=['POST'])
def generate():
    payload = request.get_json(silent=True) or {}

    from_ref = payload.get('from_ref')
    to_ref = payload.get('to_ref', 'HEAD')
    new_version = payload.get('new_version')
    previous_version = payload.get('previous_version')
    commits_payload = payload.get('commits')
    date = payload.get('date') or datetime.date.today().isoformat()
    format_ = payload.get('format', 'markdown')

    context = payload.get('context') or {}
    context.setdefault('project_name', 'YourProject')
    context.setdefault('repo_url', None)
    context.setdefault('date', date)

    if not commits_payload:
        try:
            commits = parse_commits_from_git(from_ref=from_ref, to_ref=to_ref)
        except Exception as e:
            return jsonify({'error': f'Failed to read git logs: {e}'}), 400
    else:
        # Normalize payload commits into expected structure
        commits = []
        for c in commits_payload:
            commits.append({
                'hash': c.get('hash', ''),
                'subject': c.get('subject') or c.get('message', ''),
                'body': c.get('body', '') or '',
            })

    result = generate_upgrade_notes(
        commits=commits,
        previous_version=previous_version,
        new_version=new_version,
        context=context,
    )

    if format_ == 'json':
        return jsonify(result), 200

    return jsonify({'markdown': result['markdown']}), 200

