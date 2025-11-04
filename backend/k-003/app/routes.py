from __future__ import annotations
from datetime import datetime, time as dtime
from typing import Any

from flask import Blueprint, jsonify, request, current_app
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .extensions import db, get_scheduler
from .models import Schedule
from .scheduler import schedule_all, _schedule_end_job, _on_start
from .agent import agent_manager

api_bp = Blueprint("api", __name__)


def _parse_time(value: str) -> dtime:
    try:
        hh, mm = value.strip().split(":", 1)
        return dtime(hour=int(hh), minute=int(mm))
    except Exception:
        raise ValueError("start_time must be in HH:MM format")


def _validate_timezone(tz: str) -> str:
    if not tz:
        return current_app.config.get("DEFAULT_TIMEZONE", "UTC")
    try:
        ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        raise ValueError("Invalid timezone")
    return tz


@api_bp.get("/status")
def status():
    st = agent_manager.get_state()
    jobs = get_scheduler().get_jobs()
    return jsonify(
        {
            "agent": {
                "mode": st.mode,
                "active_window_id": st.active_window_id,
                "end_at": st.end_at.isoformat() if st.end_at else None,
            },
            "jobs": [
                {
                    "id": j.id,
                    "name": j.name,
                    "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
                }
                for j in jobs
            ],
        }
    )


@api_bp.get("/schedules")
def list_schedules():
    items = Schedule.query.order_by(Schedule.id.desc()).all()
    return jsonify([i.to_dict() for i in items])


@api_bp.post("/schedules")
def create_schedule():
    data = request.get_json(force=True) or {}
    try:
        name = data["name"].strip()
        task_type = data["task_type"].strip().lower()
        tz = _validate_timezone(data.get("timezone") or current_app.config.get("DEFAULT_TIMEZONE", "UTC"))
        dow = data.get("days_of_week", "mon-sun").strip().lower()
        start_time = _parse_time(data["start_time"])  # required
        duration_minutes = data.get("duration_minutes")
        enabled = bool(data.get("enabled", True))
        if task_type == "maintenance":
            if not duration_minutes or int(duration_minutes) <= 0:
                raise ValueError("duration_minutes must be > 0 for maintenance windows")
            duration_minutes = int(duration_minutes)
        else:
            duration_minutes = None
    except KeyError as e:
        return jsonify({"error": f"Missing field: {str(e)}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    s = Schedule(
        name=name,
        task_type=task_type,
        timezone=tz,
        days_of_week=dow,
        start_time=start_time,
        duration_minutes=duration_minutes,
        enabled=enabled,
    )
    db.session.add(s)
    db.session.commit()

    schedule_all()

    return jsonify(s.to_dict()), 201


@api_bp.put("/schedules/<int:sid>")
def update_schedule(sid: int):
    s = Schedule.query.get_or_404(sid)
    data = request.get_json(force=True) or {}

    try:
        if "name" in data:
            s.name = str(data["name"]).strip()
        if "task_type" in data:
            s.task_type = str(data["task_type"]).strip().lower()
        if "timezone" in data:
            s.timezone = _validate_timezone(str(data["timezone"]))
        if "days_of_week" in data:
            s.days_of_week = str(data["days_of_week"]).strip().lower()
        if "start_time" in data:
            s.start_time = _parse_time(str(data["start_time"]))
        if s.task_type == "maintenance":
            if "duration_minutes" in data:
                dm = int(data["duration_minutes"]) if data["duration_minutes"] is not None else None
                if dm is None or dm <= 0:
                    return jsonify({"error": "duration_minutes must be > 0 for maintenance windows"}), 400
                s.duration_minutes = dm
        else:
            s.duration_minutes = None
        if "enabled" in data:
            s.enabled = bool(data["enabled"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    db.session.commit()
    schedule_all()
    return jsonify(s.to_dict())


@api_bp.delete("/schedules/<int:sid>")
def delete_schedule(sid: int):
    s = Schedule.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()

    # Remove start job for this schedule
    sched = get_scheduler()
    job_id = f"start_{sid}"
    try:
        sched.remove_job(job_id)
    except Exception:
        pass

    return jsonify({"deleted": sid})


@api_bp.post("/trigger/retraining")
def trigger_retraining():
    if not agent_manager.retraining_allowed():
        return jsonify({"status": "skipped", "reason": "maintenance active"}), 409
    from .tasks import run_retraining

    res = run_retraining()
    return jsonify(res)


@api_bp.post("/trigger/maintenance")
def trigger_maintenance():
    data = request.get_json(silent=True) or {}
    minutes = int(data.get("duration_minutes", current_app.config.get("MAINTENANCE_DEFAULT_DURATION_MIN", 60)))
    if minutes <= 0:
        return jsonify({"error": "duration_minutes must be > 0"}), 400

    now_local = datetime.now(ZoneInfo(current_app.config.get("DEFAULT_TIMEZONE", "UTC")))
    until_local = now_local + timedelta(minutes=minutes)

    # Use window_id 0 for ad-hoc
    changed = agent_manager.enter_maintenance(window_id=0, end_at=until_local)

    from .tasks import run_maintenance

    res = run_maintenance()
    _schedule_end_job(schedule_id=0, until_local=until_local)
    return jsonify({"entered": changed, "until": until_local.isoformat(), **res})


@api_bp.post("/reload")
def reload_schedules():
    schedule_all()
    return jsonify({"status": "reloaded"})

