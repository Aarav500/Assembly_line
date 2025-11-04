import os
from flask import Blueprint, current_app, request, jsonify, send_file
from werkzeug.utils import secure_filename
from db import db
from models import Dataset
from utils.checksum import sha256_of_file
from utils.storage import ensure_dir

datasets_bp = Blueprint('datasets', __name__)


@datasets_bp.post('')
def create_dataset():
    data = dict(request.form) if request.form else (request.get_json(silent=True) or {})
    name = data.get('name')
    if not name:
        return {'error': 'name is required'}, 400
    version = data.get('version')
    uri = data.get('uri')
    metadata = data.get('metadata')

    dataset = Dataset(name=name, version=version, uri=uri, metadata=metadata)

    if 'file' in request.files:
        f = request.files['file']
        filename = secure_filename(f.filename)
        storage_dir = os.path.join(current_app.config['STORAGE_DIR'], 'datasets')
        ensure_dir(storage_dir)
        path = os.path.join(storage_dir, filename)
        f.save(path)
        checksum = sha256_of_file(path)
        size = os.path.getsize(path)
        dataset.local_path = path
        dataset.checksum = checksum
        dataset.size_bytes = size

    db.session.add(dataset)
    db.session.commit()

    return dataset.to_dict(), 201


@datasets_bp.get('')
def list_datasets():
    q = Dataset.query.order_by(Dataset.created_at.desc()).all()
    return jsonify([d.to_dict() for d in q])


@datasets_bp.get('/<int:dataset_id>')
def get_dataset(dataset_id: int):
    d = Dataset.query.get_or_404(dataset_id)
    return d.to_dict()


@datasets_bp.get('/<int:dataset_id>/download')
def download_dataset(dataset_id: int):
    d = Dataset.query.get_or_404(dataset_id)
    if not d.local_path or not os.path.exists(d.local_path):
        return {'error': 'No local dataset file available for this dataset'}, 404
    return send_file(d.local_path, as_attachment=True)

