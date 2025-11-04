from flask import Blueprint, request, jsonify, g, Response
from sqlalchemy import select, and_, desc
from sqlalchemy.exc import IntegrityError
import csv
import io
from db import SessionLocal
from models import Project, AuditEvent
from audit import record_event, verify_project_chain
from utils import parse_iso_datetime, get_client_ip, get_user_agent, get_request_user_id

bp = Blueprint('api', __name__)

@bp.before_app_request
def create_session():
    g.db = SessionLocal()

@bp.teardown_app_request
def shutdown_session(exception=None):
    db = getattr(g, 'db', None)
    if db is not None:
        if exception is None:
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
        else:
            db.rollback()
        db.close()

@bp.route('/projects', methods=['POST'])
def create_project():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    p = Project(name=name)
    g.db.add(p)
    try:
        g.db.flush()
    except IntegrityError:
        g.db.rollback()
        # fetch existing
        p = g.db.execute(select(Project).where(Project.name == name)).scalar_one()
    # Optionally record project creation event
    record_event(g.db, p.id, 'project.create', metadata={'name': p.name}, user_id=get_request_user_id(), ip=get_client_ip(), user_agent=get_user_agent())
    return jsonify({'id': p.id, 'name': p.name, 'created_at': p.created_at.isoformat()})

@bp.route('/projects', methods=['GET'])
def list_projects():
    rows = g.db.execute(select(Project).order_by(Project.id.asc())).scalars().all()
    return jsonify([{'id': r.id, 'name': r.name, 'created_at': r.created_at.isoformat()} for r in rows])


def _find_project_or_404(project_id: int):
    proj = g.db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
    if not proj:
        return None
    return proj

@bp.route('/projects/<int:project_id>/audit', methods=['GET'])
def list_audit_events(project_id: int):
    proj = _find_project_or_404(project_id)
    if not proj:
        return jsonify({'error': 'project not found'}), 404

    q = select(AuditEvent).where(AuditEvent.project_id == project_id)

    types = request.args.get('type') or request.args.get('types')
    if types:
        allowed = [t.strip() for t in types.split(',') if t.strip()]
        if allowed:
            q = q.where(AuditEvent.action_type.in_(allowed))

    start = request.args.get('start')
    end = request.args.get('end')
    if start:
        try:
            dt = parse_iso_datetime(start)
            q = q.where(AuditEvent.created_at >= dt)
        except ValueError:
            return jsonify({'error': 'invalid start datetime'}), 400
    if end:
        try:
            dt = parse_iso_datetime(end)
            q = q.where(AuditEvent.created_at <= dt)
        except ValueError:
            return jsonify({'error': 'invalid end datetime'}), 400

    cursor = request.args.get('cursor')
    if cursor:
        try:
            cursor_id = int(cursor)
            q = q.where(AuditEvent.id < cursor_id)
        except ValueError:
            return jsonify({'error': 'invalid cursor'}), 400

    limit = request.args.get('limit', type=int) or 50
    limit = max(1, min(200, limit))

    q = q.order_by(desc(AuditEvent.id)).limit(limit + 1)
    rows = g.db.execute(q).scalars().all()

    has_next = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1].id if has_next and rows else None

    return jsonify({
        'project_id': project_id,
        'count': len(rows),
        'next_cursor': str(next_cursor) if next_cursor else None,
        'events': [e.to_dict() for e in rows]
    })

@bp.route('/projects/<int:project_id>/audit/export.csv', methods=['GET'])
def export_audit_csv(project_id: int):
    proj = _find_project_or_404(project_id)
    if not proj:
        return jsonify({'error': 'project not found'}), 404

    q = select(AuditEvent).where(AuditEvent.project_id == project_id)
    types = request.args.get('type') or request.args.get('types')
    if types:
        allowed = [t.strip() for t in types.split(',') if t.strip()]
        if allowed:
            q = q.where(AuditEvent.action_type.in_(allowed))
    q = q.order_by(AuditEvent.id.asc())
    rows = g.db.execute(q).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['id','project_id','action_type','user_id','ip','user_agent','created_at','prev_hash','event_hash','metadata'])
    for e in rows:
        writer.writerow([
            e.id, e.project_id, e.action_type, e.user_id or '', e.ip or '', e.user_agent or '', e.created_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ'), e.prev_hash, e.event_hash, e.metadata or '{}'
        ])
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="project_{project_id}_audit.csv"'})

@bp.route('/projects/<int:project_id>/audit/verify', methods=['GET'])
def verify_chain(project_id: int):
    proj = _find_project_or_404(project_id)
    if not proj:
        return jsonify({'error': 'project not found'}), 404
    result = verify_project_chain(g.db, project_id)
    return jsonify(result)

# Simulated action endpoints

@bp.route('/projects/<int:project_id>/actions/import', methods=['POST'])
def action_import(project_id: int):
    proj = _find_project_or_404(project_id)
    if not proj:
        return jsonify({'error': 'project not found'}), 404
    payload = request.get_json(silent=True) or {}
    ev = record_event(
        g.db, project_id, 'import', metadata=payload, user_id=get_request_user_id(), ip=get_client_ip(), user_agent=get_user_agent()
    )
    return jsonify({'status': 'ok', 'event': ev.to_dict()})

@bp.route('/projects/<int:project_id>/actions/analysis', methods=['POST'])
def action_analysis(project_id: int):
    proj = _find_project_or_404(project_id)
    if not proj:
        return jsonify({'error': 'project not found'}), 404
    payload = request.get_json(silent=True) or {}
    ev = record_event(
        g.db, project_id, 'analysis', metadata=payload, user_id=get_request_user_id(), ip=get_client_ip(), user_agent=get_user_agent()
    )
    return jsonify({'status': 'ok', 'event': ev.to_dict()})

@bp.route('/projects/<int:project_id>/actions/codegen', methods=['POST'])
def action_codegen(project_id: int):
    proj = _find_project_or_404(project_id)
    if not proj:
        return jsonify({'error': 'project not found'}), 404
    payload = request.get_json(silent=True) or {}
    ev = record_event(
        g.db, project_id, 'codegen', metadata=payload, user_id=get_request_user_id(), ip=get_client_ip(), user_agent=get_user_agent()
    )
    return jsonify({'status': 'ok', 'event': ev.to_dict()})

@bp.route('/projects/<int:project_id>/actions/deploy', methods=['POST'])
def action_deploy(project_id: int):
    proj = _find_project_or_404(project_id)
    if not proj:
        return jsonify({'error': 'project not found'}), 404
    payload = request.get_json(silent=True) or {}
    ev = record_event(
        g.db, project_id, 'deploy', metadata=payload, user_id=get_request_user_id(), ip=get_client_ip(), user_agent=get_user_agent()
    )
    return jsonify({'status': 'ok', 'event': ev.to_dict()})

