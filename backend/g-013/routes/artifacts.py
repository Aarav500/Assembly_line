import os
from flask import Blueprint, current_app, request, send_file
from werkzeug.utils import secure_filename
from db import db
from models import Artifact, Run
from utils.storage import ensure_dir
from utils.checksum import sha256_of_file

artifacts_bp = Blueprint('artifacts', __name__)


@artifacts_bp.post('')
def create_artifact():
    run_id = request.form.get('run_id')
    a_type = request.form.get('type')
    if not run_id or not a_type:
        return {'error': 'run_id and type are required'}, 400
    Run.query.get_or_404(run_id)

    if 'file' not in request.files:
        return {'error': 'file is required'}, 400

    f = request.files['file']
    filename = secure_filename(f.filename)
    storage_dir = os.path.join(current_app.config['STORAGE_DIR'], 'artifacts', str(run_id))
    ensure_dir(storage_dir)
    dest_path = os.path.join(storage_dir, filename)
    f.save(dest_path)

    checksum = sha256_of_file(dest_path)
    size = os.path.getsize(dest_path)

    artifact = Artifact(
        run_id=run_id,
        type=a_type,
        path=dest_path,
        checksum=checksum,
        size_bytes=size,
        mime_type=request.form.get('mime_type'),
        description=request.form.get('description'),
    )
    db.session.add(artifact)
    db.session.commit()
    return artifact.to_dict(), 201


@artifacts_bp.get('/<int:artifact_id>')
def get_artifact(artifact_id: int):
    a = Artifact.query.get_or_404(artifact_id)
    return a.to_dict()


@artifacts_bp.get('/<int:artifact_id>/download')
def download_artifact(artifact_id: int):
    a = Artifact.query.get_or_404(artifact_id)
    if not os.path.exists(a.path):
        return {'error': 'file not found on disk'}, 404
    return send_file(a.path, as_attachment=True)

