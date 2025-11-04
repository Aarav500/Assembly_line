from flask import Blueprint, request, jsonify, current_app
from .models import db, Taxonomy, Term, Document, DocumentTerm

api_bp = Blueprint('api', __name__)


def parse_keywords(payload):
    # Accept list of strings or list of {pattern, weight}
    if payload is None:
        return []
    out = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                pattern = str(item.get('pattern', '')).strip()
                if pattern:
                    weight = float(item.get('weight', 1.0))
                    out.append({'pattern': pattern, 'weight': weight})
            else:
                s = str(item).strip()
                if s:
                    out.append({'pattern': s, 'weight': 1.0})
    elif isinstance(payload, str):
        s = payload.strip()
        if s:
            out.append({'pattern': s, 'weight': 1.0})
    return out


@api_bp.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


# Taxonomies
@api_bp.route('/taxonomies', methods=['POST'])
def create_taxonomy():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    tax = Taxonomy(
        name=name,
        description=data.get('description'),
        default_threshold=float(data.get('default_threshold')) if data.get('default_threshold') is not None else None,
    )
    db.session.add(tax)
    db.session.commit()
    return jsonify(tax.to_dict()), 201


@api_bp.route('/taxonomies', methods=['GET'])
def list_taxonomies():
    include_terms = request.args.get('include_terms') == '1'
    taxes = Taxonomy.query.order_by(Taxonomy.name.asc()).all()
    return jsonify([t.to_dict(include_terms=include_terms) for t in taxes])


@api_bp.route('/taxonomies/<int:tax_id>', methods=['GET'])
def get_taxonomy(tax_id):
    tax = Taxonomy.query.get_or_404(tax_id)
    include_terms = request.args.get('include_terms') == '1'
    return jsonify(tax.to_dict(include_terms=include_terms))


@api_bp.route('/taxonomies/<int:tax_id>', methods=['PATCH'])
def update_taxonomy(tax_id):
    tax = Taxonomy.query.get_or_404(tax_id)
    data = request.get_json(force=True, silent=True) or {}
    if 'name' in data:
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': 'name cannot be empty'}), 400
        tax.name = name
    if 'description' in data:
        tax.description = data.get('description')
    if 'default_threshold' in data:
        v = data.get('default_threshold')
        tax.default_threshold = float(v) if v is not None else None
    db.session.commit()
    return jsonify(tax.to_dict())


@api_bp.route('/taxonomies/<int:tax_id>', methods=['DELETE'])
def delete_taxonomy(tax_id):
    tax = Taxonomy.query.get_or_404(tax_id)
    db.session.delete(tax)
    db.session.commit()
    return jsonify({'status': 'deleted'})


# Terms
@api_bp.route('/taxonomies/<int:tax_id>/terms', methods=['POST'])
def create_term(tax_id):
    tax = Taxonomy.query.get_or_404(tax_id)
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    keywords = parse_keywords(data.get('keywords'))
    term = Term(
        name=name,
        description=data.get('description'),
        taxonomy_id=tax.id,
        keywords=keywords,
        threshold=float(data.get('threshold')) if data.get('threshold') is not None else None,
        weight=float(data.get('weight')) if data.get('weight') is not None else None,
    )
    db.session.add(term)
    db.session.commit()
    return jsonify(term.to_dict()), 201


@api_bp.route('/taxonomies/<int:tax_id>/terms', methods=['GET'])
def list_terms(tax_id):
    Taxonomy.query.get_or_404(tax_id)
    terms = Term.query.filter_by(taxonomy_id=tax_id).order_by(Term.name.asc()).all()
    return jsonify([t.to_dict() for t in terms])


@api_bp.route('/terms/<int:term_id>', methods=['PATCH'])
def update_term(term_id):
    term = Term.query.get_or_404(term_id)
    data = request.get_json(force=True, silent=True) or {}
    if 'name' in data:
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': 'name cannot be empty'}), 400
        term.name = name
    if 'description' in data:
        term.description = data.get('description')
    if 'keywords' in data:
        term.keywords = parse_keywords(data.get('keywords'))
    if 'threshold' in data:
        v = data.get('threshold')
        term.threshold = float(v) if v is not None else None
    if 'weight' in data:
        v = data.get('weight')
        term.weight = float(v) if v is not None else None
    db.session.commit()
    return jsonify(term.to_dict())


@api_bp.route('/terms/<int:term_id>', methods=['DELETE'])
def delete_term(term_id):
    term = Term.query.get_or_404(term_id)
    db.session.delete(term)
    db.session.commit()
    return jsonify({'status': 'deleted'})


# Documents
@api_bp.route('/documents', methods=['POST'])
def create_document():
    data = request.get_json(force=True, silent=True) or {}
    title = (data.get('title') or '').strip()
    content = data.get('content') or ''
    if not title or not content:
        return jsonify({'error': 'title and content are required'}), 400

    doc = Document(title=title, content=content)
    db.session.add(doc)
    db.session.commit()

    auto = bool(data.get('auto_categorize'))
    taxonomy_ids = data.get('taxonomy_ids')
    min_score = data.get('min_score')

    assigned = []
    if auto:
        assigned = current_app.categorizer.categorize_document(
            doc,
            taxonomy_ids=taxonomy_ids if isinstance(taxonomy_ids, list) else None,
            min_score=float(min_score) if min_score is not None else None,
            replace=True,
        )
    return jsonify({
        'document': doc.to_dict(include_tags=True),
        'assigned_tags': [a.to_dict() for a in assigned],
    }), 201


@api_bp.route('/documents', methods=['GET'])
def list_documents():
    docs = Document.query.order_by(Document.created_at.desc()).all()
    return jsonify([d.to_dict(include_tags=True) for d in docs])


@api_bp.route('/documents/<int:doc_id>', methods=['GET'])
def get_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    return jsonify(doc.to_dict(include_tags=True))


@api_bp.route('/documents/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    db.session.delete(doc)
    db.session.commit()
    return jsonify({'status': 'deleted'})


@api_bp.route('/documents/<int:doc_id>/categorize', methods=['POST'])
def categorize_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    data = request.get_json(force=True, silent=True) or {}
    taxonomy_ids = data.get('taxonomy_ids') if isinstance(data.get('taxonomy_ids'), list) else None
    min_score = data.get('min_score')
    replace = True if data.get('replace') is None else bool(data.get('replace'))

    assigned = current_app.categorizer.categorize_document(
        doc,
        taxonomy_ids=taxonomy_ids,
        min_score=float(min_score) if min_score is not None else None,
        replace=replace,
    )
    return jsonify({
        'document': doc.to_dict(include_tags=True),
        'assigned_tags': [a.to_dict() for a in assigned],
    })


@api_bp.route('/categorize/preview', methods=['POST'])
def preview_categorization():
    data = request.get_json(force=True, silent=True) or {}
    content = data.get('content') or ''
    taxonomy_ids = data.get('taxonomy_ids') if isinstance(data.get('taxonomy_ids'), list) else None

    query = Term.query
    if taxonomy_ids:
        query = query.filter(Term.taxonomy_id.in_(taxonomy_ids))
    terms = query.all()
    tax_map = {t.id: t for t in (Taxonomy.query.all())}

    results = current_app.categorizer.categorize_text(content, terms, tax_map)
    payload = []
    for r in results:
        payload.append({
            'term': r['term'].to_dict(),
            'score': round(r['score'], 4),
            'matched_keywords': r['matched_keywords'],
            'taxonomy': tax_map[r['term'].taxonomy_id].to_dict(),
        })
    return jsonify(payload)


@api_bp.route('/search', methods=['GET'])
def search_by_term():
    # Find documents by term name or term_id
    term_id = request.args.get('term_id', type=int)
    term_name = request.args.get('term_name')

    if not term_id and not term_name:
        return jsonify({'error': 'Provide term_id or term_name'}), 400

    term = None
    if term_id:
        term = Term.query.get_or_404(term_id)
    else:
        t = Term.query.filter(Term.name.ilike(term_name)).first()
        if not t:
            return jsonify([])
        term = t

    links = DocumentTerm.query.filter_by(term_id=term.id).all()
    doc_ids = [l.document_id for l in links]
    docs = Document.query.filter(Document.id.in_(doc_ids)).all()
    return jsonify({
        'term': term.to_dict(),
        'documents': [d.to_dict(include_tags=True) for d in docs]
    })

