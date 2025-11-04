from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta, timezone
from dateutil.tz import gettz
from reports import generate_team_report, generate_project_report

scheduler = None


def _prev_day_range(now):
    start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def _prev_week_range(now):
    # ISO week: start Monday
    start = (now - timedelta(days=now.weekday()+7)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return start, end


def _tz(timezone_name):
    return gettz(timezone_name) or gettz('UTC')


def init_scheduler(app):
    global scheduler
    if scheduler is not None:
        return scheduler

    tz = _tz(app.config.get('TIMEZONE', 'UTC'))
    scheduler = BackgroundScheduler(timezone=tz)

    @scheduler.scheduled_job(CronTrigger(hour=0, minute=30))
    def daily_reports():
        with app.app_context():
            now = datetime.now(tz)
            start, end = _prev_day_range(now)
            generate_team_report(start, end, app.config['REPORTS_DIR'])
            generate_project_report(start, end, app.config['REPORTS_DIR'])
            app.logger.info(f"Generated daily reports for {start.date()}")

    @scheduler.scheduled_job(CronTrigger(day_of_week='mon', hour=1, minute=0))
    def weekly_reports():
        with app.app_context():
            now = datetime.now(tz)
            start, end = _prev_week_range(now)
            generate_team_report(start, end, app.config['REPORTS_DIR'])
            generate_project_report(start, end, app.config['REPORTS_DIR'])
            app.logger.info(f"Generated weekly reports for week starting {start.date()}")

    scheduler.start()
    app.logger.info("Scheduler started")
    return scheduler

