from flask import Blueprint, current_app, jsonify, request, render_template, redirect, url_for
from datetime import datetime
from models import db, BacklogItem
from todo_extractor import scan_and_update_backlog


bp = Blueprint('routes', __name__)


@bp.route('/')
def index():
    status = request.args.get('status', 'open')
    tag = request.args.get('tag')
    q = BacklogItem.query
    if status:
        q = q.filter_by(status=status)
    if tag:
        q = q.filter_by(tag=tag)
    items = q.order_by(BacklogItem.file_path.asc(), BacklogItem.line_number.asc()).all()
    counts = {
        'open': BacklogItem.query.filter_by(status='open').count(),
        'resolved': BacklogItem.query.filter_by(status='resolved').count(),
    }
    return render_template('index.html', items=items, status=status, tag=tag, counts=counts)


@bp.route('/api/scan', methods=['POST'])
def api_scan():
    result = scan_and_update_backlog(current_app)
    return jsonify(result)


@bp.route('/api/items', methods=['GET'])
def api_items():
    status = request.args.get('status')
    tag = request.args.get('tag')
    q = BacklogItem.query
    if status:
        q = q.filter_by(status=status)
    if tag:
        q = q.filter_by(tag=tag)
    items = [i.to_dict() for i in q.order_by(BacklogItem.updated_at.desc()).all()]
    return jsonify({'items': items, 'count': len(items)})


@bp.route('/api/items/<int:item_id>', methods=['GET'])
def api_item_get(item_id):
    item = BacklogItem.query.get_or_404(item_id)
    return jsonify(item.to_dict())


@bp.route('/api/items/<int:item_id>/resolve', methods=['POST'])
def api_item_resolve(item_id):
    item = BacklogItem.query.get_or_404(item_id)
    item.status = 'resolved'
    item.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'ok', 'item': item.to_dict()})


@bp.route('/scan', methods=['POST'])
def scan_action():
    result = scan_and_update_backlog(current_app)
    return redirect(url_for('routes.index'))

