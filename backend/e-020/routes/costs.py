from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify
from sqlalchemy import func, and_
from database import db
from models import CostRecord, Resource, ResourceTag
from services.cost_engine import accrue_last_full_hour, accrue_for_window

costs_bp = Blueprint('costs', __name__)


def parse_iso(dt_str: str):
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


@costs_bp.route('/costs/accrue', methods=['POST'])
def accrue_costs():
    data = request.get_json(silent=True) or {}
    hour = data.get('hour')
    start = data.get('from') or data.get('start')
    end = data.get('to') or data.get('end')

    if hour:
        dt = parse_iso(hour)
        if not dt:
            return jsonify({'error': 'Invalid hour format'}), 400
        start_hour = dt.replace(minute=0, second=0, microsecond=0)
        end_hour = start_hour + timedelta(hours=1)
        res = accrue_for_window(start_hour, end_hour)
        return jsonify(res)

    if start and end:
        s = parse_iso(start)
        e = parse_iso(end)
        if not s or not e:
            return jsonify({'error': 'Invalid from/to format'}), 400
        s = s.replace(minute=0, second=0, microsecond=0)
        e = e.replace(minute=0, second=0, microsecond=0)
        res = accrue_for_window(s, e)
        return jsonify(res)

    # Default: last full hour
    res = accrue_last_full_hour()
    return jsonify(res)


@costs_bp.route('/costs', methods=['GET'])
def list_costs():
    tenant_id = request.args.get('tenant_id', type=int)
    project_id = request.args.get('project_id', type=int)
    resource_id = request.args.get('resource_id', type=int)
    start = request.args.get('from')
    end = request.args.get('to')

    q = CostRecord.query
    if tenant_id:
        q = q.filter(CostRecord.tenant_id == tenant_id)
    if project_id:
        q = q.filter(CostRecord.project_id == project_id)
    if resource_id:
        q = q.filter(CostRecord.resource_id == resource_id)
    if start:
        s = parse_iso(start)
        if not s:
            return jsonify({'error': 'Invalid from format'}), 400
        s = s.replace(minute=0, second=0, microsecond=0)
        q = q.filter(CostRecord.start_hour >= s)
    if end:
        e = parse_iso(end)
        if not e:
            return jsonify({'error': 'Invalid to format'}), 400
        e = e.replace(minute=0, second=0, microsecond=0)
        q = q.filter(CostRecord.start_hour < e)

    q = q.order_by(CostRecord.start_hour.desc(), CostRecord.id.desc())
    items = q.limit(1000).all()
    return jsonify([c.to_dict() for c in items])


@costs_bp.route('/costs/summary', methods=['GET'])
def cost_summary():
    group_by = request.args.get('group_by', 'tenant')
    start = request.args.get('from')
    end = request.args.get('to')

    q = db.session.query(CostRecord)
    if start:
        s = parse_iso(start)
        if not s:
            return jsonify({'error': 'Invalid from format'}), 400
        s = s.replace(minute=0, second=0, microsecond=0)
        q = q.filter(CostRecord.start_hour >= s)
    if end:
        e = parse_iso(end)
        if not e:
            return jsonify({'error': 'Invalid to format'}), 400
        e = e.replace(minute=0, second=0, microsecond=0)
        q = q.filter(CostRecord.start_hour < e)

    if group_by == 'tenant':
        rows = db.session.query(
            CostRecord.tenant_id.label('key'),
            func.sum(CostRecord.amount).label('amount'),
            func.min(CostRecord.currency).label('currency')
        ).select_from(CostRecord).filter(*q._criterion) if q._criterion is not None else db.session.query(CostRecord.tenant_id.label('key'), func.sum(CostRecord.amount).label('amount'), func.min(CostRecord.currency).label('currency')).select_from(CostRecord)
        if q._criterion is not None:
            rows = rows.filter(q._criterion)
        rows = rows.group_by(CostRecord.tenant_id).all()
        return jsonify([{'group': 'tenant', 'key': r.key, 'amount': round(r.amount, 6), 'currency': r.currency} for r in rows])

    if group_by == 'project':
        rows = db.session.query(
            CostRecord.project_id.label('key'),
            func.sum(CostRecord.amount).label('amount'),
            func.min(CostRecord.currency).label('currency')
        ).select_from(CostRecord)
        if q._criterion is not None:
            rows = rows.filter(q._criterion)
        rows = rows.group_by(CostRecord.project_id).all()
        return jsonify([{'group': 'project', 'key': r.key, 'amount': round(r.amount, 6), 'currency': r.currency} for r in rows])

    if group_by.startswith('tag:'):
        tag_key = group_by.split(':', 1)[1]
        # join ResourceTag via Resource
        base = db.session.query(
            ResourceTag.value.label('key'),
            func.sum(CostRecord.amount).label('amount'),
            func.min(CostRecord.currency).label('currency')
        ).select_from(CostRecord).join(Resource, Resource.id == CostRecord.resource_id).join(ResourceTag, and_(ResourceTag.resource_id == Resource.id, ResourceTag.key == tag_key))
        if q._criterion is not None:
            base = base.filter(q._criterion)
        rows = base.group_by(ResourceTag.value).all()
        return jsonify([{'group': f'tag:{tag_key}', 'key': r.key, 'amount': round(r.amount, 6), 'currency': r.currency} for r in rows])

    return jsonify({'error': 'Invalid group_by. Use tenant, project, or tag:<key>'}), 400

