from datetime import datetime
from flask import Blueprint, request, jsonify
from db import db
from models import Run, RunDataset, Dataset, CodeVersion, Environment, Bundle
from utils.bundler import create_bundle_for_run

runs_bp = Blueprint('runs', __name__)


@runs_bp.post('')
def create_run():
    data = request.get_json(force=True)
    name = data.get('name')
    if not name:
        return {'error': 'name is required'}, 400

    code_version_id = data.get('code_version_id')
    environment_id = data.get('environment_id')

    if code_version_id:
        CodeVersion.query.get_or_404(code_version_id)
    if environment_id:
        Environment.query.get_or_404(environment_id)

    run = Run(
        name=name,
        status=data.get('status', 'created'),
        random_seed=data.get('random_seed'),
        parameters=data.get('parameters'),
        metrics=data.get('metrics'),
        notes=data.get('notes'),
        code_version_id=code_version_id,
        environment_id=environment_id,
    )

    db.session.add(run)
    db.session.flush()

    # Link datasets if provided
    for ds_link in data.get('datasets', []) or []:
        dataset_id = ds_link.get('dataset_id')
        role = ds_link.get('role')
        if not dataset_id or not role:
            db.session.rollback()
            return {'error': 'Each dataset link requires dataset_id and role'}, 400
        Dataset.query.get_or_404(dataset_id)
        rd = RunDataset(run_id=run.id, dataset_id=dataset_id, role=role, snapshot_path=ds_link.get('snapshot_path'))
        db.session.add(rd)

    db.session.commit()
    return run.to_dict(), 201


@runs_bp.get('')
def list_runs():
    q = Run.query.order_by(Run.created_at.desc()).all()
    return jsonify([r.to_dict(include_children=False) for r in q])


@runs_bp.get('/<int:run_id>')
def get_run(run_id: int):
    r = Run.query.get_or_404(run_id)
    return r.to_dict()


@runs_bp.post('/<int:run_id>/update')
def update_run(run_id: int):
    r = Run.query.get_or_404(run_id)
    data = request.get_json(force=True)
    for field in ['status', 'random_seed', 'parameters', 'metrics', 'notes']:
        if field in data:
            setattr(r, field, data[field])
    db.session.commit()
    return r.to_dict()


@runs_bp.post('/<int:run_id>/finish')
def finish_run(run_id: int):
    r = Run.query.get_or_404(run_id)
    data = request.get_json(silent=True) or {}
    r.status = data.get('status', 'finished')
    r.ended_at = datetime.utcnow()
    if 'metrics' in data:
        r.metrics = data['metrics']
    db.session.commit()
    return r.to_dict()


@runs_bp.post('/<int:run_id>/datasets')
def add_run_dataset(run_id: int):
    r = Run.query.get_or_404(run_id)
    data = request.get_json(force=True)
    dataset_id = data.get('dataset_id')
    role = data.get('role')
    if not dataset_id or not role:
        return {'error': 'dataset_id and role are required'}, 400
    Dataset.query.get_or_404(dataset_id)
    rd = RunDataset(run_id=run_id, dataset_id=dataset_id, role=role, snapshot_path=data.get('snapshot_path'))
    db.session.add(rd)
    db.session.commit()
    return rd.to_dict(), 201


@runs_bp.post('/<int:run_id>/bundle')
def bundle_run(run_id: int):
    run = Run.query.get_or_404(run_id)
    bundle_path, checksum, size = create_bundle_for_run(run)
    bundle = Bundle(run_id=run.id, path=bundle_path, checksum=checksum, size_bytes=size)
    db.session.add(bundle)
    db.session.commit()
    return bundle.to_dict(), 201


@runs_bp.get('/<int:run_id>/bundles')
def list_run_bundles(run_id: int):
    run = Run.query.get_or_404(run_id)
    return [b.to_dict() for b in run.bundles]


@runs_bp.get('/<int:run_id>/manifest')
def get_run_manifest(run_id: int):
    run = Run.query.get_or_404(run_id)
    from utils.bundler import build_manifest
    manifest = build_manifest(run)
    return manifest

