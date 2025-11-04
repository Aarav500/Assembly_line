from datetime import datetime, timedelta
from typing import Any, Dict, List
import os
from flask import Blueprint, jsonify, request, current_app, abort
from sqlalchemy import and_, or_
from . import db
from .models import Release, Stage
from .utils import parse_iso_datetime_utc_naive, isoformat_utc, get_auth_token_from_request, require_auth, stable_percentage


api_bp = Blueprint('api', __name__)


@api_bp.route('/health', methods=['GET'])
def health() -> Any:
    return jsonify({'status': 'ok', 'time_utc': isoformat_utc(datetime.utcnow())})


@api_bp.route('/releases', methods=['GET'])
def list_releases() -> Any:
    releases = Release.query.order_by(Release.created_at.desc()).all()
    return jsonify({'releases': [r.to_dict() for r in releases]})


@api_bp.route('/releases', methods=['POST'])
def create_release() -> Any:
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    version = data.get('version')
    description = data.get('description')
    stages_data = data.get('stages', [])

    if not name or not version:
        return jsonify({'error': 'name and version are required'}), 400

    release = Release(name=name, version=version, description=description)
    db.session.add(release)
    db.session.flush()  # to get release.id

    for s in stages_data:
        try:
            start_at = parse_iso_datetime_utc_naive(s.get('start_at'))
        except Exception:
            db.session.rollback()
            return jsonify({'error': f"invalid start_at for stage {s}"}), 400
        end_at = None
        if s.get('end_at'):
            try:
                end_at = parse_iso_datetime_utc_naive(s.get('end_at'))
            except Exception:
                db.session.rollback()
                return jsonify({'error': f"invalid end_at for stage {s}"}), 400
        duration_minutes = s.get('duration_minutes')
        if duration_minutes and not end_at:
            end_at = start_at + timedelta(minutes=int(duration_minutes))

        stage = Stage(
            release_id=release.id,
            name=s.get('name') or f"stage-{len(release.stages) + 1}",
            target=s.get('target'),
            percentage=s.get('percentage'),
            ci_job_name=s.get('ci_job_name'),
            start_at=start_at,
            end_at=end_at,
            status='pending',
        )
        db.session.add(stage)

    db.session.commit()
    return jsonify({'release': release.to_dict()}), 201


@api_bp.route('/releases/<int:release_id>', methods=['GET'])
def get_release(release_id: int) -> Any:
    r = Release.query.get_or_404(release_id)
    return jsonify({'release': r.to_dict()})


@api_bp.route('/releases/by-name/<string:name>/<string:version>', methods=['GET'])
def get_release_by_name(name: str, version: str) -> Any:
    r = Release.query.filter_by(name=name, version=version).first()
    if not r:
        return jsonify({'error': 'not found'}), 404
    return jsonify({'release': r.to_dict()})


@api_bp.route('/releases/<int:release_id>/current', methods=['GET'])
def current_stage(release_id: int) -> Any:
    now = datetime.utcnow()
    stages = Stage.query.filter_by(release_id=release_id).order_by(Stage.start_at).all()
    active = None
    for st in stages:
        if st.is_active_time(now):
            active = st
            break
    return jsonify({'now_utc': isoformat_utc(now), 'active_stage': active.to_dict() if active else None})


@api_bp.route('/releases/<int:release_id>/stages', methods=['GET'])
def list_stages(release_id: int) -> Any:
    stages = Stage.query.filter_by(release_id=release_id).order_by(Stage.start_at).all()
    return jsonify({'stages': [s.to_dict() for s in stages]})


@api_bp.route('/releases/<int:release_id>/stages', methods=['POST'])
def add_stage(release_id: int) -> Any:
    r = Release.query.get_or_404(release_id)
    data = request.get_json(silent=True) or {}
    try:
        start_at = parse_iso_datetime_utc_naive(data.get('start_at'))
    except Exception:
        return jsonify({'error': 'invalid start_at'}), 400
    end_at = None
    if data.get('end_at'):
        try:
            end_at = parse_iso_datetime_utc_naive(data.get('end_at'))
        except Exception:
            return jsonify({'error': 'invalid end_at'}), 400
    duration_minutes = data.get('duration_minutes')
    if duration_minutes and not end_at:
        end_at = start_at + timedelta(minutes=int(duration_minutes))

    stage = Stage(
        release_id=r.id,
        name=data.get('name') or f"stage-{len(r.stages) + 1}",
        target=data.get('target'),
        percentage=data.get('percentage'),
        ci_job_name=data.get('ci_job_name'),
        start_at=start_at,
        end_at=end_at,
        status='pending',
    )
    db.session.add(stage)
    db.session.commit()
    return jsonify({'stage': stage.to_dict()}), 201


@api_bp.route('/releases/<int:release_id>/is-enabled', methods=['GET'])
def is_enabled(release_id: int) -> Any:
    user_key = request.args.get('user_key')
    if not user_key:
        return jsonify({'error': 'user_key required'}), 400
    now = datetime.utcnow()
    stages = Stage.query.filter_by(release_id=release_id).order_by(Stage.start_at.desc()).all()
    curr = None
    for st in stages:
        if st.is_active_time(now):
            curr = st
            break
    if not curr:
        return jsonify({'enabled': False, 'reason': 'no_active_stage'})
    if curr.percentage is None:
        return jsonify({'enabled': True, 'reason': 'no_percentage_restriction'})
    pct = int(curr.percentage)
    enabled = stable_percentage(user_key) < pct
    return jsonify({'enabled': enabled, 'stage': curr.to_dict(), 'user_key': user_key})


@api_bp.route('/ci/ready', methods=['GET'])
@require_auth
def ci_ready() -> Any:
    now = datetime.utcnow()
    window_min = int(current_app.config.get('TRIGGER_WINDOW_MINUTES', 10))
    limit = int(request.args.get('limit', 10))

    # Mark overdue pending stages as skipped if they are past the window and were never triggered
    overdue = Stage.query.filter(
        and_(Stage.status == 'pending', Stage.end_at.isnot(None), Stage.end_at < now - timedelta(minutes=window_min))
    ).all()
    for st in overdue:
        st.status = 'skipped'
        st.updated_at = now
    if overdue:
        db.session.commit()

    q = (
        Stage.query.join(Release, Stage.release_id == Release.id)
        .filter(
            and_(
                Stage.status == 'pending',
                Stage.start_at <= now,
                or_(Stage.end_at.is_(None), Stage.end_at > now),
            )
        )
        .order_by(Stage.start_at)
    )

    ready: List[Stage] = []
    for st in q.all():
        if st.last_triggered_at is None and st.within_trigger_window(now, window_min):
            ready.append(st)
        if len(ready) >= limit:
            break

    tasks: List[Dict[str, Any]] = []
    for st in ready:
        st.status = 'triggered'
        st.last_triggered_at = now
        st.updated_at = now
        tasks.append({
            'release_id': st.release_id,
            'release_name': st.release.name,
            'version': st.release.version,
            'stage_id': st.id,
            'stage_name': st.name,
            'target': st.target,
            'percentage': st.percentage,
            'ci_job_name': st.ci_job_name,
            'start_at': isoformat_utc(st.start_at),
            'end_at': isoformat_utc(st.end_at) if st.end_at else None,
        })

    if ready:
        db.session.commit()

    return jsonify({'now_utc': isoformat_utc(now), 'tasks': tasks})


@api_bp.route('/ci/report', methods=['POST'])
@require_auth
def ci_report() -> Any:
    data = request.get_json(silent=True) or {}
    stage_id = data.get('stage_id')
    status = data.get('status')  # completed|failed|skipped
    logs_url = data.get('logs_url')
    if not stage_id or status not in {'completed', 'failed', 'skipped'}:
        return jsonify({'error': 'stage_id and valid status are required'}), 400

    st = Stage.query.get(stage_id)
    if not st:
        return jsonify({'error': 'stage not found'}), 404

    st.status = status
    st.logs_url = logs_url
    st.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'stage': st.to_dict()})

