from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import desc
from .models import db, SnapshotSchedule, Snapshot, Runbook, Drill, DrillSchedule
from .services.scheduler import reschedule_snapshot_job, remove_snapshot_job, reschedule_drill_job, remove_drill_job, schedule_one_time_drill
from .services.snapshots import queue_snapshot_now

api_bp = Blueprint('api', __name__)


def bad_request(msg, code=400):
    return jsonify({"error": msg}), code


@api_bp.post('/schedules')
def create_schedule():
    data = request.get_json(force=True)
    name = data.get('name')
    source_path = data.get('source_path')
    cron = data.get('cron')
    interval_minutes = data.get('interval_minutes')
    retention = data.get('retention', 7)
    enabled = bool(data.get('enabled', True))
    snapshot_format = data.get('snapshot_format', 'tar.gz')
    tags = data.get('tags', {})

    if not name or not source_path:
        return bad_request('name and source_path are required')
    if not cron and not interval_minutes:
        return bad_request('either cron or interval_minutes is required')
    try:
        retention = int(retention)
    except Exception:
        return bad_request('retention must be integer')

    schedule = SnapshotSchedule(
        name=name,
        source_path=source_path,
        cron=cron,
        interval_minutes=interval_minutes,
        retention=retention,
        enabled=enabled,
        snapshot_format=snapshot_format,
        tags=tags,
    )
    db.session.add(schedule)
    db.session.commit()

    reschedule_snapshot_job(schedule.id)

    return jsonify(schedule.to_dict()), 201


@api_bp.get('/schedules')
def list_schedules():
    schedules = SnapshotSchedule.query.order_by(SnapshotSchedule.id.asc()).all()
    return jsonify([s.to_dict() for s in schedules])


@api_bp.get('/schedules/<int:schedule_id>')
def get_schedule(schedule_id):
    s = SnapshotSchedule.query.get_or_404(schedule_id)
    snapshots = Snapshot.query.filter_by(schedule_id=schedule_id).order_by(desc(Snapshot.created_at)).limit(20).all()
    data = s.to_dict()
    data['recent_snapshots'] = [snap.to_dict() for snap in snapshots]
    return jsonify(data)


@api_bp.patch('/schedules/<int:schedule_id>')
def update_schedule(schedule_id):
    s = SnapshotSchedule.query.get_or_404(schedule_id)
    data = request.get_json(force=True)
    for field in ['name', 'source_path', 'cron', 'interval_minutes', 'retention', 'enabled', 'snapshot_format', 'tags']:
        if field in data:
            setattr(s, field, data[field])
    db.session.commit()

    reschedule_snapshot_job(schedule_id)

    return jsonify(s.to_dict())


@api_bp.delete('/schedules/<int:schedule_id>')
def delete_schedule(schedule_id):
    s = SnapshotSchedule.query.get_or_404(schedule_id)
    remove_snapshot_job(schedule_id)
    # Note: Does not delete snapshot files for safety
    db.session.delete(s)
    db.session.commit()
    return jsonify({'deleted': True})


@api_bp.post('/schedules/<int:schedule_id>/run')
def run_snapshot_now(schedule_id):
    s = SnapshotSchedule.query.get_or_404(schedule_id)
    job_id = queue_snapshot_now(schedule_id)
    return jsonify({'queued': True, 'job_id': job_id})


@api_bp.get('/snapshots')
def list_snapshots():
    schedule_id = request.args.get('schedule_id')
    q = Snapshot.query
    if schedule_id:
        q = q.filter_by(schedule_id=int(schedule_id))
    snaps = q.order_by(desc(Snapshot.created_at)).limit(100).all()
    return jsonify([s.to_dict() for s in snaps])


@api_bp.post('/runbooks')
def create_runbook():
    data = request.get_json(force=True)
    name = data.get('name')
    if not name:
        return bad_request('name required')
    description = data.get('description')
    steps = data.get('steps', [])
    enabled = bool(data.get('enabled', True))

    rb = Runbook(name=name, description=description, steps_json=steps, enabled=enabled)
    db.session.add(rb)
    db.session.commit()
    return jsonify(rb.to_dict()), 201


@api_bp.get('/runbooks')
def list_runbooks():
    rbs = Runbook.query.order_by(Runbook.id.asc()).all()
    return jsonify([r.to_dict() for r in rbs])


@api_bp.get('/runbooks/<int:runbook_id>')
def get_runbook(runbook_id):
    rb = Runbook.query.get_or_404(runbook_id)
    return jsonify(rb.to_dict())


@api_bp.patch('/runbooks/<int:runbook_id>')
def update_runbook(runbook_id):
    rb = Runbook.query.get_or_404(runbook_id)
    data = request.get_json(force=True)
    for field in ['name', 'description', 'steps', 'enabled']:
        if field in data:
            if field == 'steps':
                rb.steps_json = data['steps']
            else:
                setattr(rb, field, data[field])
    db.session.commit()
    return jsonify(rb.to_dict())


@api_bp.delete('/runbooks/<int:runbook_id>')
def delete_runbook(runbook_id):
    rb = Runbook.query.get_or_404(runbook_id)
    db.session.delete(rb)
    db.session.commit()
    return jsonify({'deleted': True})


@api_bp.post('/runbooks/<int:runbook_id>/drill')
def start_drill(runbook_id):
    rb = Runbook.query.get_or_404(runbook_id)
    drill = Drill(runbook_id=rb.id, status='PENDING')
    db.session.add(drill)
    db.session.commit()

    job_id = schedule_one_time_drill(drill.id)

    return jsonify({'queued': True, 'drill_id': drill.id, 'job_id': job_id})


@api_bp.get('/drills')
def list_drills():
    drills = Drill.query.order_by(desc(Drill.id)).limit(100).all()
    return jsonify([d.to_dict() for d in drills])


@api_bp.get('/drills/<int:drill_id>')
def get_drill(drill_id):
    d = Drill.query.get_or_404(drill_id)
    return jsonify(d.to_dict())


@api_bp.post('/drill_schedules')
def create_drill_schedule():
    data = request.get_json(force=True)
    name = data.get('name')
    runbook_id = data.get('runbook_id')
    cron = data.get('cron')
    interval_minutes = data.get('interval_minutes')
    enabled = bool(data.get('enabled', True))
    if not name or not runbook_id:
        return bad_request('name and runbook_id required')
    if not cron and not interval_minutes:
        return bad_request('either cron or interval_minutes required')

    ds = DrillSchedule(name=name, runbook_id=runbook_id, cron=cron, interval_minutes=interval_minutes, enabled=enabled)
    db.session.add(ds)
    db.session.commit()

    reschedule_drill_job(ds.id)

    return jsonify(ds.to_dict()), 201


@api_bp.get('/drill_schedules')
def list_drill_schedules():
    schedules = DrillSchedule.query.order_by(DrillSchedule.id.asc()).all()
    return jsonify([s.to_dict() for s in schedules])


@api_bp.patch('/drill_schedules/<int:schedule_id>')
def update_drill_schedule(schedule_id):
    ds = DrillSchedule.query.get_or_404(schedule_id)
    data = request.get_json(force=True)
    for field in ['name', 'runbook_id', 'cron', 'interval_minutes', 'enabled']:
        if field in data:
            setattr(ds, field, data[field])
    db.session.commit()

    reschedule_drill_job(schedule_id)

    return jsonify(ds.to_dict())


@api_bp.delete('/drill_schedules/<int:schedule_id>')
def delete_drill_schedule(schedule_id):
    ds = DrillSchedule.query.get_or_404(schedule_id)
    remove_drill_job(schedule_id)
    db.session.delete(ds)
    db.session.commit()
    return jsonify({'deleted': True})

