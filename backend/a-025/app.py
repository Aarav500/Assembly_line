import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify, abort
from sqlalchemy import func
from database import db
from models import Project, Snapshot, Checkpoint, AuditLog


def create_app():
    app = Flask(__name__)

    # Config
    db_url = os.getenv('DATABASE_URL', 'sqlite:///data.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    def get_project_or_404(project_id: int) -> Project:
        project = Project.query.get(project_id)
        if not project:
            abort(404, description='Project not found')
        return project

    def validate_json():
        if not request.is_json:
            abort(400, description='Expected application/json')
        return request.get_json(silent=True) or {}

    def audit(project_id: int, action: str, meta: dict | None = None):
        log = AuditLog(project_id=project_id, action=action, meta=meta or {})
        db.session.add(log)

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': 'bad_request', 'message': getattr(error, 'description', str(error))}), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'not_found', 'message': getattr(error, 'description', str(error))}), 404

    @app.errorhandler(409)
    def conflict(error):
        return jsonify({'error': 'conflict', 'message': getattr(error, 'description', str(error))}), 409

    @app.errorhandler(500)
    def server_error(error):
        return jsonify({'error': 'server_error', 'message': 'An unexpected error occurred'}), 500

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok'})

    # Project endpoints
    @app.route('/projects', methods=['POST'])
    def create_project():
        payload = validate_json()
        name = (payload.get('name') or '').strip()
        description = payload.get('description')
        state = payload.get('state') or {}
        if not name:
            abort(400, description='name is required')
        project = Project(name=name, description=description, current_state=state, current_version=0)
        db.session.add(project)
        db.session.flush()  # to get project.id
        # create initial snapshot as bookmark (read-only) if requested
        initial_bookmark = payload.get('initial_bookmark')
        if initial_bookmark:
            snap = Snapshot(
                project_id=project.id,
                label=str(initial_bookmark)[:255],
                data=state,
                version=1,
                is_bookmark=True,
                is_read_only=True,
            )
            project.current_version = 1
            db.session.add(snap)
        audit(project.id, 'create_project', {'name': name})
        db.session.commit()
        return jsonify({'project': project.to_dict()})

    @app.route('/projects', methods=['GET'])
    def list_projects():
        projects = Project.query.order_by(Project.created_at.desc()).all()
        return jsonify({'projects': [p.to_dict(include_state=False) for p in projects]})

    @app.route('/projects/<int:project_id>', methods=['GET'])
    def get_project(project_id: int):
        project = get_project_or_404(project_id)
        return jsonify({'project': project.to_dict()})

    @app.route('/projects/<int:project_id>/state', methods=['GET'])
    def get_state(project_id: int):
        project = get_project_or_404(project_id)
        return jsonify({'project_id': project.id, 'current_state': project.current_state, 'current_version': project.current_version})

    @app.route('/projects/<int:project_id>/state', methods=['PUT'])
    def update_state(project_id: int):
        project = get_project_or_404(project_id)
        payload = validate_json()
        state = payload.get('state')
        if state is None:
            abort(400, description='state is required')
        project.current_state = state
        audit(project.id, 'update_state', {'version': project.current_version})
        db.session.commit()
        return jsonify({'project': project.to_dict()})

    # Snapshot endpoints (includes bookmarks)
    @app.route('/projects/<int:project_id>/snapshots', methods=['POST'])
    def create_snapshot(project_id: int):
        project = get_project_or_404(project_id)
        payload = validate_json()
        label = payload.get('label')
        is_bookmark = bool(payload.get('bookmark', False))
        is_read_only = bool(payload.get('read_only', is_bookmark))
        data = payload.get('state') if payload.get('state') is not None else project.current_state
        if is_bookmark and label:
            # prevent duplicate bookmark labels per project
            existing = Snapshot.query.filter_by(project_id=project.id, is_bookmark=True, label=label).first()
            if existing:
                abort(409, description='Bookmark label already exists for this project')
        new_version = project.current_version + 1
        snap = Snapshot(
            project_id=project.id,
            label=(str(label)[:255] if label else None),
            data=data,
            version=new_version,
            is_bookmark=is_bookmark,
            is_read_only=is_read_only,
        )
        project.current_version = new_version
        db.session.add(snap)
        audit(project.id, 'create_snapshot', {'snapshot_id': None, 'version': new_version, 'bookmark': is_bookmark, 'label': label})
        db.session.commit()
        return jsonify({'snapshot': snap.to_dict(), 'project_version': project.current_version})

    @app.route('/projects/<int:project_id>/snapshots', methods=['GET'])
    def list_snapshots(project_id: int):
        get_project_or_404(project_id)
        snaps = Snapshot.query.filter_by(project_id=project_id).order_by(Snapshot.created_at.desc()).all()
        return jsonify({'snapshots': [s.to_dict() for s in snaps]})

    @app.route('/projects/<int:project_id>/bookmarks', methods=['POST'])
    def create_bookmark(project_id: int):
        project = get_project_or_404(project_id)
        payload = validate_json()
        label = payload.get('label')
        if not label:
            abort(400, description='label is required for bookmarks')
        data = payload.get('state') if payload.get('state') is not None else project.current_state
        existing = Snapshot.query.filter_by(project_id=project.id, is_bookmark=True, label=label).first()
        if existing:
            abort(409, description='Bookmark label already exists for this project')
        new_version = project.current_version + 1
        snap = Snapshot(
            project_id=project.id,
            label=str(label)[:255],
            data=data,
            version=new_version,
            is_bookmark=True,
            is_read_only=True,
        )
        project.current_version = new_version
        db.session.add(snap)
        audit(project.id, 'create_bookmark', {'label': label, 'version': new_version})
        db.session.commit()
        return jsonify({'bookmark': snap.to_dict(), 'project_version': project.current_version})

    @app.route('/projects/<int:project_id>/bookmarks', methods=['GET'])
    def list_bookmarks(project_id: int):
        get_project_or_404(project_id)
        snaps = Snapshot.query.filter_by(project_id=project_id, is_bookmark=True).order_by(Snapshot.created_at.desc()).all()
        return jsonify({'bookmarks': [s.to_dict() for s in snaps]})

    @app.route('/projects/<int:project_id>/snapshots/<int:snapshot_id>', methods=['DELETE'])
    def delete_snapshot(project_id: int, snapshot_id: int):
        get_project_or_404(project_id)
        snap = Snapshot.query.filter_by(project_id=project_id, id=snapshot_id).first()
        if not snap:
            abort(404, description='Snapshot not found')
        if snap.is_read_only:
            abort(409, description='Cannot delete read-only snapshot/bookmark')
        db.session.delete(snap)
        audit(project_id, 'delete_snapshot', {'snapshot_id': snapshot_id})
        db.session.commit()
        return jsonify({'deleted': True})

    # Checkpoint endpoints
    @app.route('/projects/<int:project_id>/checkpoints', methods=['POST'])
    def create_checkpoint(project_id: int):
        project = get_project_or_404(project_id)
        payload = validate_json()
        label = payload.get('label')
        data = payload.get('state') if payload.get('state') is not None else project.current_state
        # compute next index
        next_idx = (db.session.query(func.coalesce(func.max(Checkpoint.index), 0)).filter(Checkpoint.project_id == project.id).scalar() or 0) + 1
        ck = Checkpoint(project_id=project.id, label=(str(label)[:255] if label else None), data=data, index=next_idx)
        db.session.add(ck)
        audit(project.id, 'create_checkpoint', {'checkpoint_id': None, 'index': next_idx, 'label': label})
        db.session.commit()
        return jsonify({'checkpoint': ck.to_dict()})

    @app.route('/projects/<int:project_id>/checkpoints', methods=['GET'])
    def list_checkpoints(project_id: int):
        get_project_or_404(project_id)
        cks = Checkpoint.query.filter_by(project_id=project_id).order_by(Checkpoint.index.desc()).all()
        return jsonify({'checkpoints': [c.to_dict() for c in cks]})

    @app.route('/projects/<int:project_id>/checkpoints/<int:checkpoint_id>', methods=['DELETE'])
    def delete_checkpoint(project_id: int, checkpoint_id: int):
        get_project_or_404(project_id)
        ck = Checkpoint.query.filter_by(project_id=project_id, id=checkpoint_id).first()
        if not ck:
            abort(404, description='Checkpoint not found')
        db.session.delete(ck)
        audit(project_id, 'delete_checkpoint', {'checkpoint_id': checkpoint_id})
        db.session.commit()
        return jsonify({'deleted': True})

    # Rollback endpoint
    @app.route('/projects/<int:project_id>/rollback', methods=['POST'])
    def rollback(project_id: int):
        project = get_project_or_404(project_id)
        payload = validate_json()
        snapshot_id = payload.get('snapshot_id')
        checkpoint_id = payload.get('checkpoint_id')
        bookmark_label = payload.get('bookmark_label')
        create_snapshot_after = bool(payload.get('create_snapshot', True))
        snapshot_label = payload.get('snapshot_label') or 'rollback'

        if not snapshot_id and not checkpoint_id and not bookmark_label:
            abort(400, description='Provide snapshot_id, checkpoint_id, or bookmark_label')

        source_state = None
        source_meta = {}

        if snapshot_id:
            snap = Snapshot.query.filter_by(project_id=project.id, id=snapshot_id).first()
            if not snap:
                abort(404, description='Snapshot not found')
            source_state = snap.data
            source_meta = {'type': 'snapshot', 'id': snap.id, 'label': snap.label, 'version': snap.version}
        elif bookmark_label:
            snap = Snapshot.query.filter_by(project_id=project.id, is_bookmark=True, label=bookmark_label).first()
            if not snap:
                abort(404, description='Bookmark not found')
            source_state = snap.data
            source_meta = {'type': 'bookmark', 'id': snap.id, 'label': snap.label, 'version': snap.version}
        elif checkpoint_id:
            ck = Checkpoint.query.filter_by(project_id=project.id, id=checkpoint_id).first()
            if not ck:
                abort(404, description='Checkpoint not found')
            source_state = ck.data
            source_meta = {'type': 'checkpoint', 'id': ck.id, 'label': ck.label, 'index': ck.index}

        if source_state is None:
            abort(400, description='Rollback source could not be resolved')

        # Apply rollback by setting project state
        project.current_state = source_state

        # Optionally create a new snapshot to record the rollback state
        created_snapshot = None
        if create_snapshot_after:
            new_version = project.current_version + 1
            snap = Snapshot(
                project_id=project.id,
                label=str(snapshot_label)[:255] if snapshot_label else None,
                data=source_state,
                version=new_version,
                is_bookmark=False,
                is_read_only=False,
            )
            project.current_version = new_version
            db.session.add(snap)
            created_snapshot = snap
        audit(project.id, 'rollback', {'from': source_meta, 'created_snapshot': bool(created_snapshot)})
        db.session.commit()
        resp = {
            'project': project.to_dict(),
            'rolled_back_from': source_meta,
        }
        if created_snapshot:
            resp['snapshot'] = created_snapshot.to_dict()
        return jsonify(resp)

    # Audit logs
    @app.route('/projects/<int:project_id>/audit', methods=['GET'])
    def list_audit(project_id: int):
        get_project_or_404(project_id)
        logs = AuditLog.query.filter_by(project_id=project_id).order_by(AuditLog.created_at.desc()).limit(200).all()
        return jsonify({'audit': [l.to_dict() for l in logs]})

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=True)

