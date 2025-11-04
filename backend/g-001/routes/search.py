from flask import request, jsonify
from sqlalchemy import or_
from models import Model, ModelVersion, Dataset, MetadataRevision
from . import api

@api.route('/search', methods=['GET'])
def search():
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'error': 'q is required'}), 400
    like = f"%{q}%"

    models = Model.query.filter(or_(Model.name.ilike(like), Model.description.ilike(like))).limit(25).all()

    versions = ModelVersion.query.filter(
        or_(ModelVersion.version.ilike(like), ModelVersion.code_commit.ilike(like), ModelVersion.created_by.ilike(like))
    ).limit(25).all()

    # search in latest metadata revision JSON as string via LIKE
    meta_hits = (
        MetadataRevision.query
        .filter(MetadataRevision.revision_num == 1)
        .subquery()
    )
    # For simplicity, search across all revisions
    meta_versions = MetadataRevision.query.filter(MetadataRevision.data.cast(str).ilike(like)).limit(50).all()
    meta_version_ids = list({mr.model_version_id for mr in meta_versions})

    datasets = Dataset.query.filter(or_(Dataset.name.ilike(like), Dataset.description.ilike(like), Dataset.uri.ilike(like))).limit(25).all()

    return jsonify({
        'models': [m.to_dict() for m in models],
        'versions': [v.to_dict(include_metadata=True) for v in versions],
        'versions_from_metadata': meta_version_ids,
        'datasets': [d.to_dict() for d in datasets],
    })

