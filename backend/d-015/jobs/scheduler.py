import atexit
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from jobs import tasks


def init_scheduler(app):
    tz = app.config["TIMEZONE"]

    job_defaults = {
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 60 * 60,  # 1 hour
    }

    scheduler = BackgroundScheduler(timezone=tz, job_defaults=job_defaults)

    # Nightly integration tests
    integration_trigger = CronTrigger.from_crontab(app.config["INTEGRATION_CRON"], timezone=tz)
    scheduler.add_job(
        func=tasks.integration_tests_job,
        trigger=integration_trigger,
        args=[app],
        id="nightly_integration_tests",
        replace_existing=True,
        name="Nightly Integration Tests",
    )

    # Nightly load tests
    load_trigger = CronTrigger.from_crontab(app.config["LOADTEST_CRON"], timezone=tz)
    scheduler.add_job(
        func=tasks.load_tests_job,
        trigger=load_trigger,
        args=[app],
        id="nightly_load_tests",
        replace_existing=True,
        name="Nightly Load Tests",
    )

    scheduler.start()

    atexit.register(lambda: scheduler.shutdown(wait=False))

    app.extensions["scheduler"] = scheduler

    app.logger.setLevel(getattr(logging, app.config.get("LOG_LEVEL", "INFO")))

    return scheduler

