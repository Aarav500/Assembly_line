from __future__ import annotations
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo
from flask import current_app


db = SQLAlchemy()
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        tz = ZoneInfo(current_app.config.get("DEFAULT_TIMEZONE", "UTC"))
        _scheduler = BackgroundScheduler(timezone=tz)
        _scheduler.start()
    return _scheduler


def init_scheduler(app):
    # ensure scheduler instantiated with correct timezone
    with app.app_context():
        sched = get_scheduler()
        # nothing else to do
        return sched

