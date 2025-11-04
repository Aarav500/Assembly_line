import os
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

_scheduler = None


def _send_digest_job(app):
    from digest import build_digest
    from emailer import send_digest_to_owners
    with app.app_context():
        data = build_digest(app.config)
        send_digest_to_owners(app, data, None)


def init_scheduler(app):
    global _scheduler

    if not app.config.get("DIGEST_ENABLED", True):
        app.logger.info("Digest scheduler disabled by configuration")
        return

    # Avoid duplicate scheduler in reloader environments
    if app.config.get("SCHEDULER_STARTED"):
        return

    _scheduler = BackgroundScheduler(daemon=True)
    trigger = CronTrigger(
        day_of_week=app.config.get("DIGEST_DAY_OF_WEEK", "mon"),
        hour=app.config.get("DIGEST_HOUR", "8"),
        minute=app.config.get("DIGEST_MINUTE", "0"),
    )

    _scheduler.add_job(
        _send_digest_job,
        trigger=trigger,
        args=[app],
        id="weekly_security_dependency_digest",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    _scheduler.start()
    atexit.register(lambda: _scheduler.shutdown(wait=False))
    app.config["SCHEDULER_STARTED"] = True
    app.logger.info(
        "Digest scheduler started: day_of_week=%s hour=%s minute=%s",
        app.config.get("DIGEST_DAY_OF_WEEK", "mon"),
        app.config.get("DIGEST_HOUR", "8"),
        app.config.get("DIGEST_MINUTE", "0"),
    )

