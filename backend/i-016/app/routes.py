import json
from flask import Blueprint, current_app, request, jsonify, send_file, abort
from sqlalchemy import asc, desc
from . import db
from .models import Evidence, Bundle, BundleItem
from .utils import save_upload, compute_bundle_hash, zip_bundle_in_memory

bp = Blueprint('api', __name__)


def parse_tags(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    s = str(value).strip()
    if not s:
        return []
    # Try JSON first
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [str(v).strip() for v in parsed if str(v).strip()]
    except Exception:
        pass
    # Fallback: comma-separated
    return [t.strip() for t in s.split(',') if t.strip()]


def parse_meta(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {}


@bp.post('/upload')
def upload_evidence():
    if 'file' not in request.files:
        return jsonify({'error': 'file field is required'}), 400
    f = request.files['file']
    if f.filename is None or f.filename == '':
        return jsonify({'error': 'filename is required'}), 400

    audit_id = request.form.get('audit_id')
    tags = parse_tags(request.form.get('tags'))
    meta = parse_meta(request.form.get('meta') or request.form.get('metadata'))

    saved = save_upload(current_app.config['STORAGE_DIR'], f, 'evidence')

    ev = Evidence(
        original_filename=saved['original_filename'],
        stored_filename=saved['stored_filename'],
        relative_path=saved['relative_path'],
        content_type=f.mimetype,
        size_bytes=saved['size_bytes'],
        sha256=saved['sha256'],
        tags=tags,
        audit_id=audit_id,
        meta_json=meta,
    )
    db.session.add(ev)
    db.session.commit()

    return jsonify({'evidence': ev.to_dict()}), 201


@bp.get('/evidences')
def list_evidences():
    q = Evidence.query
    audit_id = request.args.get('audit_id')
    tag = request.args.get('tag')
    search = request.args.get('q')
    sort = request.args.get('sort', 'uploaded_at')
    order = request.args.get('order', 'desc')

    if audit_id:
        q = q.filter(Evidence.audit_id == audit_id)
    if tag:
        q = q.filter(Evidence.tags.contains([tag]))
    if search:
        like = f"%{search}%"
        q = q.filter((Evidence.original_filename.ilike(like)) | (Evidence.meta_json.cast(db.String).ilike(like)))

    if sort == 'size':
        q = q.order_by(desc(Evidence.size_bytes) if order == 'desc' else asc(Evidence.size_bytes))
    elif sort == 'filename':
        q = q.order_by(desc(Evidence.original_filename) if order == 'desc' else asc(Evidence.original_filename))
    else:
        q = q.order_by(desc(Evidence.uploaded_at) if order == 'desc' else asc(Evidence.uploaded_at))

    limit = min(int(request.args.get('limit', 50)), 500)
    offset = int(request.args.get('offset', 0))

    items = q.offset(offset).limit(limit).all()
    return jsonify({
        'items': [ev.to_dict() for ev in items],
        'count': len(items),
        'offset': offset,
        'limit': limit,
    })


@bp.get('/evidences/<int:evidence_id>')
def get_evidence(evidence_id):
    ev = Evidence.query.get_or_404(evidence_id)
    return jsonify({'evidence': ev.to_dict()})


@bp.post('/bundles')
def create_bundle():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    if not name:
        return jsonify({'error': 'name is required'}), 400
    description = data.get('description')
    audit_id = data.get('audit_id')
    evidence_ids = data.get('evidence_ids') or []
    if not isinstance(evidence_ids, list) or not all(isinstance(i, int) for i in evidence_ids):
        return jsonify({'error': 'evidence_ids must be a list of integers'}), 400

    evidence_rows = Evidence.query.filter(Evidence.id.in_(evidence_ids)).all() if evidence_ids else []
    if evidence_ids and len(evidence_rows) != len(set(evidence_ids)):
        return jsonify({'error': 'one or more evidence_ids not found'}), 404

    bundle = Bundle(name=name, description=description, audit_id=audit_id)
    db.session.add(bundle)
    db.session.flush()

    for ev in evidence_rows:
        db.session.add(BundleItem(bundle_id=bundle.id, evidence_id=ev.id))

    bundle.item_count = len(evidence_rows)
    bundle.bundle_hash = compute_bundle_hash([ev.sha256 for ev in evidence_rows]) if evidence_rows else None

    db.session.commit()

    return jsonify({'bundle': bundle.to_dict(include_items=True)}), 201


@bp.get('/bundles')
def list_bundles():
    q = Bundle.query
    audit_id = request.args.get('audit_id')
    if audit_id:
        q = q.filter(Bundle.audit_id == audit_id)

    sort = request.args.get('sort', 'created_at')
    order = request.args.get('order', 'desc')
    if sort == 'name':
        q = q.order_by(desc(Bundle.name) if order == 'desc' else asc(Bundle.name))
    else:
        q = q.order_by(desc(Bundle.created_at) if order == 'desc' else asc(Bundle.created_at))

    limit = min(int(request.args.get('limit', 50)), 500)
    offset = int(request.args.get('offset', 0))

    items = q.offset(offset).limit(limit).all()
    return jsonify({
        'items': [b.to_dict() for b in items],
        'count': len(items),
        'offset': offset,
        'limit': limit,
    })


@bp.get('/bundles/<int:bundle_id>')
def get_bundle(bundle_id):
    b = Bundle.query.get_or_404(bundle_id)
    include_items = request.args.get('include_items', 'false').lower() in ('1', 'true', 'yes')
    return jsonify({'bundle': b.to_dict(include_items=include_items)})


@bp.get('/bundles/<int:bundle_id>/export')
@bp.get('/export/<int:bundle_id>')
def export_bundle(bundle_id):
    b = Bundle.query.get_or_404(bundle_id)
    evidence_rows = [bi.evidence for bi in b.items]
    if not evidence_rows:
        return jsonify({'error': 'bundle contains no evidence'}), 400

    mem_zip = zip_bundle_in_memory(current_app.config['STORAGE_DIR'], b, evidence_rows)
    filename = f"bundle_{b.id}_{b.name.replace(' ', '_')}.zip"
    return send_file(
        mem_zip,
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename
    )


@bp.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'file too large'}), 413

