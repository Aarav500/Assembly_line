import os
from flask import Blueprint, current_app, request
from werkzeug.utils import secure_filename
from db import db
from models import CodeVersion
from utils.storage import ensure_dir

code_bp = Blueprint('code_versions', __name__)


@code_bp.post('')
def create_code_version():
    data = dict(request.form) if request.form else (request.get_json(silent=True) or {})
    commit_hash = data.get('commit_hash')
    if not commit_hash:
        return {'error': 'commit_hash is required'}, 400
    repo_url = data.get('repo_url')
    branch = data.get('branch')
    notes = data.get('notes')

    code = CodeVersion(repo_url=repo_url, commit_hash=commit_hash, branch=branch, notes=notes)

    if 'patch' in request.files:
        f = request.files['patch']
        filename = secure_filename(f.filename) or f'patch-{commit_hash}.diff'
        storage_dir = os.path.join(current_app.config['STORAGE_DIR'], 'patches')
        ensure_dir(storage_dir)
        path = os.path.join(storage_dir, filename)
        f.save(path)
        code.patch_path = path

    db.session.add(code)
    db.session.commit()
    return code.to_dict(), 201


@code_bp.get('')
def list_code_versions():
    q = CodeVersion.query.order_by(CodeVersion.created_at.desc()).all()
    return [c.to_dict() for c in q]


@code_bp.get('/<int:code_id>')
def get_code_version(code_id: int):
    c = CodeVersion.query.get_or_404(code_id)
    return c.to_dict()

