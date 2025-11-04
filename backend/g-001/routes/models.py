from flask import request, jsonify
from sqlalchemy import or_, select
from db import db
from models import Model, Tag, ModelVersion, MetadataRevision, Artifact, LineageEdge, Dataset
from utils import normalize_stage
from . import api

# Helper functions

def get_or_create_tag(name: str) -> Tag:
    t = Tag.query.filter_by(name=name).first()
    if not t:
        t = Tag(name=name)
        db.session.add(t)
    return t

@api.route('/models', methods=['POST'])
def create_model():
    payload = request.get_json(force=True) or {}
    name = payload.get('name')
    if not name:
        return jsonify({'error': 'name is required'}), 400
    description = payload.get('description')
    tags = payload.get('tags') or []
    if Model.query.filter_by(name=name).first():
        return jsonify({'error': f"model with name '{name}' already exists"}), 409
    m = Model(name=name, description=description)
    for tag_name in tags:
        m.tags.append(get_or_create_tag(tag_name))
    db.session.add(m)
    db.session.commit()
    return jsonify(m.to_dict(with_versions=False)), 201

@api.route('/models', methods=['GET'])
def list_models():
    q = request.args.get('q')
    query = Model.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Model.name.ilike(like), Model.description.ilike(like)))
    models = query.order_by(Model.created_at.desc()).all()
    return jsonify([m.to_dict(with_versions=False) for m in models])

@api.route('/models/<int:model_id>', methods=['GET'])
def get_model(model_id):
    m = Model.query.get_or_404(model_id)
    return jsonify(m.to_dict(with_versions=True))

@api.route('/models/<int:model_id>', methods=['PATCH'])
def update_model(model_id):
    m = Model.query.get_or_404(model_id)
    payload = request.get_json(force=True) or {}
    if 'name' in payload:
        new_name = payload['name']
        if new_name != m.name and Model.query.filter_by(name=new_name).first():
            return jsonify({'error': 'name already exists'}), 409
        m.name = new_name
    if 'description' in payload:
        m.description = payload['description']
    if 'archived' in payload:
        m.archived = bool(payload['archived'])
    if 'tags' in payload and isinstance(payload['tags'], list):
        m.tags.clear()
        for tag_name in payload['tags']:
            m.tags.append(get_or_create_tag(tag_name))
    db.session.commit()
    return jsonify(m.to_dict(with_versions=True))

@api.route('/models/<int:model_id>/versions', methods=['POST'])
def create_model_version(model_id):
    model = Model.query.get_or_404(model_id)
    payload = request.get_json(force=True) or {}
    version_label = payload.get('version')
    stage = normalize_stage(payload.get('stage'))
    code_commit = payload.get('code_commit')
    created_by = payload.get('created_by') or payload.get('author')
    metadata = payload.get('metadata') or {}
    metadata_message = payload.get('metadata_message') or payload.get('message')

    if version_label:
        if ModelVersion.query.filter_by(model_id=model.id, version=version_label).first():
            return jsonify({'error': f"version '{version_label}' already exists for model"}), 409

    mv = ModelVersion(model_id=model.id, version=version_label, stage=stage, code_commit=code_commit, created_by=created_by)
    db.session.add(mv)
    db.session.flush()  # get mv.id

    # Create initial metadata revision
    mr = MetadataRevision(model_version_id=mv.id, revision_num=1, data=metadata, message=metadata_message, author=created_by)
    db.session.add(mr)

    # Artifacts
    for art in payload.get('artifacts', []) or []:
        a = Artifact(
            model_version_id=mv.id,
            type=art.get('type') or 'artifact',
            uri=art.get('uri'),
            sha256=art.get('sha256'),
            size=art.get('size'),
            extra=art.get('extra'),
        )
        if not a.uri:
            return jsonify({'error': 'artifact.uri is required'}), 400
        db.session.add(a)

    # Lineage: parents (model versions)
    for pid in payload.get('parents', []) or []:
        e = LineageEdge(parent_type='model_version', parent_id=int(pid), child_type='model_version', child_id=mv.id, relation='derives_from')
        db.session.add(e)

    # Lineage: datasets
    for ds in payload.get('datasets', []) or []:
        ds_id = ds.get('id')
        relation = ds.get('relation') or 'trained_on'
        if not ds_id:
            # Optionally create dataset inline by name
            ds_name = ds.get('name')
            if ds_name:
                existing = Dataset.query.filter_by(name=ds_name).first()
                if existing:
                    ds_id = existing.id
                else:
                    new_ds = Dataset(name=ds_name, uri=ds.get('uri'), description=ds.get('description'), sha256=ds.get('sha256'), metadata=ds.get('metadata'))
                    db.session.add(new_ds)
                    db.session.flush()
                    ds_id = new_ds.id
            else:
                return jsonify({'error': 'dataset id or name required in datasets entries'}), 400
        e = LineageEdge(parent_type='dataset', parent_id=int(ds_id), child_type='model_version', child_id=mv.id, relation=relation)
        db.session.add(e)

    db.session.commit()
    return jsonify(mv.to_dict(include_metadata=True, include_lineage=True)), 201

@api.route('/models/<int:model_id>/versions', methods=['GET'])
def list_model_versions(model_id):
    Model.query.get_or_404(model_id)
    versions = ModelVersion.query.filter_by(model_id=model_id).order_by(ModelVersion.created_at.desc()).all()
    return jsonify([v.to_dict(include_metadata=True) for v in versions])

@api.route('/models/<int:model_id>/versions/<int:version_id>', methods=['GET'])
def get_model_version(model_id, version_id):
    Model.query.get_or_404(model_id)
    mv = ModelVersion.query.filter_by(model_id=model_id, id=version_id).first_or_404()
    return jsonify(mv.to_dict(include_metadata=True, include_lineage=True))

@api.route('/models/<int:model_id>/versions/<int:version_id>', methods=['PATCH'])
def update_model_version(model_id, version_id):
    Model.query.get_or_404(model_id)
    mv = ModelVersion.query.filter_by(model_id=model_id, id=version_id).first_or_404()
    payload = request.get_json(force=True) or {}

    if 'version' in payload:
        new_label = payload['version']
        if new_label != mv.version and ModelVersion.query.filter_by(model_id=model_id, version=new_label).first():
            return jsonify({'error': 'version label already exists for model'}), 409
        mv.version = new_label

    if 'stage' in payload:
        mv.stage = normalize_stage(payload.get('stage'))

    if 'code_commit' in payload:
        mv.code_commit = payload['code_commit']

    # Add metadata revision if provided
    if 'metadata' in payload:
        data = payload['metadata'] or {}
        message = payload.get('metadata_message') or payload.get('message')
        author = payload.get('author') or payload.get('created_by')
        last = MetadataRevision.query.filter_by(model_version_id=mv.id).order_by(MetadataRevision.revision_num.desc()).first()
        rev_num = 1 + (last.revision_num if last else 0)
        mr = MetadataRevision(model_version_id=mv.id, revision_num=rev_num, data=data, message=message, author=author)
        db.session.add(mr)

    # Add artifacts
    for art in payload.get('artifacts', []) or []:
        a = Artifact(
            model_version_id=mv.id,
            type=art.get('type') or 'artifact',
            uri=art.get('uri'),
            sha256=art.get('sha256'),
            size=art.get('size'),
            extra=art.get('extra'),
        )
        if not a.uri:
            return jsonify({'error': 'artifact.uri is required'}), 400
        db.session.add(a)

    # Append lineage edges if provided
    for pid in payload.get('parents', []) or []:
        e = LineageEdge(parent_type='model_version', parent_id=int(pid), child_type='model_version', child_id=mv.id, relation='derives_from')
        db.session.add(e)

    for ds in payload.get('datasets', []) or []:
        ds_id = ds.get('id')
        relation = ds.get('relation') or 'trained_on'
        if not ds_id:
            ds_name = ds.get('name')
            if ds_name:
                existing = Dataset.query.filter_by(name=ds_name).first()
                if existing:
                    ds_id = existing.id
                else:
                    new_ds = Dataset(name=ds_name, uri=ds.get('uri'), description=ds.get('description'), sha256=ds.get('sha256'), metadata=ds.get('metadata'))
                    db.session.add(new_ds)
                    db.session.flush()
                    ds_id = new_ds.id
            else:
                return jsonify({'error': 'dataset id or name required in datasets entries'}), 400
        e = LineageEdge(parent_type='dataset', parent_id=int(ds_id), child_type='model_version', child_id=mv.id, relation=relation)
        db.session.add(e)

    db.session.commit()
    return jsonify(mv.to_dict(include_metadata=True, include_lineage=True))

@api.route('/versions/<int:version_id>/metadata/revisions', methods=['GET'])
def list_metadata_revisions(version_id):
    mv = ModelVersion.query.get_or_404(version_id)
    return jsonify([mr.to_dict(include_data=True) for mr in mv.metadata_revisions])

@api.route('/versions/<int:version_id>/metadata/revisions', methods=['POST'])
def add_metadata_revision(version_id):
    mv = ModelVersion.query.get_or_404(version_id)
    payload = request.get_json(force=True) or {}
    data = payload.get('data') or payload.get('metadata')
    if data is None:
        return jsonify({'error': 'metadata (or data) is required'}), 400
    message = payload.get('message')
    author = payload.get('author')
    last = MetadataRevision.query.filter_by(model_version_id=mv.id).order_by(MetadataRevision.revision_num.desc()).first()
    rev_num = 1 + (last.revision_num if last else 0)
    mr = MetadataRevision(model_version_id=mv.id, revision_num=rev_num, data=data, message=message, author=author)
    db.session.add(mr)
    db.session.commit()
    return jsonify(mr.to_dict(include_data=True)), 201

@api.route('/models/<int:model_id>/versions/<int:version_id>/artifacts', methods=['POST'])
def add_artifact(model_id, version_id):
    Model.query.get_or_404(model_id)
    mv = ModelVersion.query.filter_by(model_id=model_id, id=version_id).first_or_404()
    payload = request.get_json(force=True) or {}
    uri = payload.get('uri')
    if not uri:
        return jsonify({'error': 'uri is required'}), 400
    a = Artifact(
        model_version_id=mv.id,
        type=payload.get('type') or 'artifact',
        uri=uri,
        sha256=payload.get('sha256'),
        size=payload.get('size'),
        extra=payload.get('extra'),
    )
    db.session.add(a)
    db.session.commit()
    return jsonify(a.to_dict()), 201

