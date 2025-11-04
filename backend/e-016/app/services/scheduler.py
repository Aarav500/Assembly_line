import logging
from datetime import datetime
from flask import current_app
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from ..models import db, SnapshotSchedule, DrillSchedule
from .snapshots import snapshot_job
from .runbooks import drill_job

logger = logging.getLogger(__name__)


SCHEDULER_KEY = 'scheduler'


def get_scheduler():
    return current_app.extensions[SCHEDULER_KEY]


def init_scheduler(app):
    job_defaults = app.config.get('SCHEDULER_JOB_DEFAULTS', {})
    scheduler = BackgroundScheduler(job_defaults=job_defaults, timezone=app.config.get('TIMEZONE', 'UTC'))
    scheduler.start(paused=False)
    app.extensions[SCHEDULER_KEY] = scheduler
    logger.info('Scheduler started')


def _snapshot_job_id(schedule_id: int) -> str:
    return f'snapshot:{schedule_id}'


def _drill_job_id(schedule_id: int) -> str:
    return f'drill:{schedule_id}'


def reschedule_snapshot_job(schedule_id: int):
    """Create or update APScheduler job for a snapshot schedule based on DB row."""
    scheduler = get_scheduler()
    sched = SnapshotSchedule.query.get(schedule_id)
    if not sched:
        return

    # Remove existing job if any
    try:
        scheduler.remove_job(_snapshot_job_id(schedule_id))
    except Exception:
        pass

    if not sched.enabled:
        logger.info('Snapshot schedule %s disabled, not scheduling job', schedule_id)
        _update_next_run(sched, None)
        return

    trigger = None
    if sched.cron:
        try:
            trigger = CronTrigger.from_crontab(sched.cron, timezone=current_app.config.get('TIMEZONE', 'UTC'))
        except Exception as e:
            logger.error('Invalid cron for schedule %s: %s', schedule_id, e)
            _update_next_run(sched, None)
            return
    elif sched.interval_minutes:
        trigger = IntervalTrigger(minutes=int(sched.interval_minutes), timezone=current_app.config.get('TIMEZONE', 'UTC'))
    else:
        logger.error('Schedule %s has neither cron nor interval', schedule_id)
        _update_next_run(sched, None)
        return

    job = scheduler.add_job(snapshot_job, trigger=trigger, id=_snapshot_job_id(schedule_id), args=[schedule_id], replace_existing=True)
    _update_next_run(sched, job.next_run_time)


def remove_snapshot_job(schedule_id: int):
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(_snapshot_job_id(schedule_id))
    except Exception:
        pass


def reschedule_drill_job(drill_schedule_id: int):
    scheduler = get_scheduler()
    ds = DrillSchedule.query.get(drill_schedule_id)
    if not ds:
        return

    try:
        scheduler.remove_job(_drill_job_id(drill_schedule_id))
    except Exception:
        pass

    if not ds.enabled:
        _update_drill_next_run(ds, None)
        return

    trigger = None
    if ds.cron:
        try:
            trigger = CronTrigger.from_crontab(ds.cron, timezone=current_app.config.get('TIMEZONE', 'UTC'))
        except Exception as e:
            logger.error('Invalid cron for drill schedule %s: %s', drill_schedule_id, e)
            _update_drill_next_run(ds, None)
            return
    elif ds.interval_minutes:
        trigger = IntervalTrigger(minutes=int(ds.interval_minutes), timezone=current_app.config.get('TIMEZONE', 'UTC'))
    else:
        _update_drill_next_run(ds, None)
        return

    job = scheduler.add_job(drill_job, trigger=trigger, id=_drill_job_id(drill_schedule_id), args=[ds.runbook_id, drill_schedule_id], replace_existing=True)
    _update_drill_next_run(ds, job.next_run_time)


def remove_drill_job(drill_schedule_id: int):
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(_drill_job_id(drill_schedule_id))
    except Exception:
        pass


def load_jobs_from_db():
    # Rehydrate snapshot jobs
    for s in SnapshotSchedule.query.all():
        reschedule_snapshot_job(s.id)
    # Rehydrate drill jobs
    for ds in DrillSchedule.query.all():
        reschedule_drill_job(ds.id)


def _update_next_run(schedule: SnapshotSchedule, next_run_time):
    schedule.next_run_at = next_run_time
    db.session.commit()


def _update_drill_next_run(ds: DrillSchedule, next_run_time):
    ds.next_run_at = next_run_time
    db.session.commit()


def schedule_one_time_drill(drill_id: int) -> str:
    scheduler = get_scheduler()
    job_id = f"drill-run:{drill_id}"
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass
    scheduler.add_job(drill_job, trigger=DateTrigger(run_date=datetime.utcnow()), id=job_id, args=[None, None, drill_id])
    return job_id

