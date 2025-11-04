from __future__ import annotations
from datetime import datetime, timedelta, time as dtime
from typing import Optional

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from flask import current_app
from zoneinfo import ZoneInfo

from .extensions import get_scheduler, db
from .models import Schedule
from .tasks import run_maintenance, run_retraining
from .agent import agent_manager


def _schedule_id_start(sid: int) -> str:
    return f"start_{sid}"


def _schedule_id_end(sid: int, until_dt: datetime) -> str:
    return f"end_{sid}_{int(until_dt.timestamp())}"


def schedule_all() -> None:
    """(Re)schedule all recurring start jobs from DB without touching one-off end jobs."""
    sched = get_scheduler()
    # remove existing start_* jobs
    for job in list(sched.get_jobs()):
        if job.id.startswith("start_"):
            sched.remove_job(job.id)

    schedules = Schedule.query.filter_by(enabled=True).all()
    for s in schedules:
        _schedule_start_job(s)

    current_app.logger.info(f"Scheduled {len(schedules)} start jobs")


def _schedule_start_job(s: Schedule) -> None:
    sched = get_scheduler()
    tz = ZoneInfo(s.timezone or current_app.config.get("DEFAULT_TIMEZONE", "UTC"))

    trig = CronTrigger(
        day_of_week=s.days_of_week,
        hour=s.start_time.hour,
        minute=s.start_time.minute,
        timezone=tz,
    )
    job_id = _schedule_id_start(s.id)

    def start_wrapper(schedule_id: int):
        _on_start(schedule_id)

    sched.add_job(start_wrapper, trigger=trig, id=job_id, replace_existing=True, kwargs={"schedule_id": s.id}, name=f"start:{s.name}")


def _on_start(schedule_id: int) -> None:
    s: Optional[Schedule] = Schedule.query.get(schedule_id)
    if not s or not s.enabled:
        return
    tz = ZoneInfo(s.timezone or current_app.config.get("DEFAULT_TIMEZONE", "UTC"))
    now_local = datetime.now(tz)

    if s.task_type == "maintenance":
        duration = s.duration_minutes or current_app.config.get("MAINTENANCE_DEFAULT_DURATION_MIN", 60)
        until_local = now_local + timedelta(minutes=duration)
        # Set maintenance mode
        changed = agent_manager.enter_maintenance(window_id=s.id, end_at=until_local)
        # Run maintenance tasks at the start
        try:
            run_maintenance()
            s.last_run_at = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            current_app.logger.exception(f"Maintenance task error for schedule {s.id}: {e}")
        # Schedule end of maintenance as one-off job in local timezone
        _schedule_end_job(schedule_id=s.id, until_local=until_local)
        if changed:
            current_app.logger.info(f"Maintenance window started for schedule {s.id} until {until_local.isoformat()}")
    else:  # retraining
        if not agent_manager.retraining_allowed():
            current_app.logger.info("Skipping retraining; currently in maintenance window and retrain not allowed.")
            return
        try:
            run_retraining()
            s.last_run_at = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            current_app.logger.exception(f"Retraining task error for schedule {s.id}: {e}")


def _schedule_end_job(schedule_id: int, until_local: datetime) -> None:
    sched = get_scheduler()
    trig = DateTrigger(run_date=until_local)
    job_id = _schedule_id_end(schedule_id, until_local)

    def end_wrapper(sid: int):
        _on_end(sid)

    sched.add_job(end_wrapper, trigger=trig, id=job_id, kwargs={"sid": schedule_id}, name=f"end:{schedule_id}")


def _on_end(schedule_id: int) -> None:
    agent_manager.exit_maintenance(window_id=schedule_id)


# Helpers

def _today_start_dt(s: Schedule, now_local: datetime) -> datetime:
    return now_local.replace(hour=s.start_time.hour, minute=s.start_time.minute, second=0, microsecond=0)


def _is_now_in_window(s: Schedule, now_local: datetime) -> bool:
    if s.task_type != "maintenance" or not s.enabled:
        return False
    # Use CronTrigger to compute last start before now
    trig = CronTrigger(
        day_of_week=s.days_of_week,
        hour=s.start_time.hour,
        minute=s.start_time.minute,
        timezone=now_local.tzinfo,
    )
    # find last fire within last 14 days
    last = None
    prev = now_local - timedelta(days=14)
    candidate = trig.get_next_fire_time(None, prev)
    while candidate and candidate <= now_local:
        last = candidate
        candidate = trig.get_next_fire_time(last, candidate)
    if not last:
        return False
    duration = s.duration_minutes or current_app.config.get("MAINTENANCE_DEFAULT_DURATION_MIN", 60)
    return last <= now_local <= (last + timedelta(minutes=duration))


def initial_state_check() -> None:
    """If app starts during a maintenance window, enter maintenance and schedule end properly."""
    schedules = Schedule.query.filter_by(enabled=True, task_type="maintenance").all()
    for s in schedules:
        tz = ZoneInfo(s.timezone or current_app.config.get("DEFAULT_TIMEZONE", "UTC"))
        now_local = datetime.now(tz)
        if _is_now_in_window(s, now_local):
            duration = s.duration_minutes or current_app.config.get("MAINTENANCE_DEFAULT_DURATION_MIN", 60)
            # Compute end of current window based on last start before now
            trig = CronTrigger(
                day_of_week=s.days_of_week,
                hour=s.start_time.hour,
                minute=s.start_time.minute,
                timezone=tz,
            )
            last = None
            prev = now_local - timedelta(days=14)
            candidate = trig.get_next_fire_time(None, prev)
            while candidate and candidate <= now_local:
                last = candidate
                candidate = trig.get_next_fire_time(last, candidate)
            if last:
                until_local = last + timedelta(minutes=duration)
                agent_manager.enter_maintenance(window_id=s.id, end_at=until_local)
                # Ensure an end job exists for this window
                _schedule_end_job(schedule_id=s.id, until_local=until_local)
                current_app.logger.info(
                    f"App started mid-window; enforced maintenance for schedule {s.id} until {until_local.isoformat()}"
                )

