import threading
import time
from flask import current_app
from .models import db, Source
from .services.checker import check_source


def scheduler_loop(app):
    interval = app.config.get('SCHEDULER_INTERVAL_SECONDS', 60)
    while True:
        try:
            with app.app_context():
                due_sources = Source.query.filter_by(active=True).all()
                for s in due_sources:
                    if s.is_due():
                        check_source(s)
        except Exception as e:
            app.logger.exception(f"Scheduler error: {e}")
        time.sleep(interval)


def start_scheduler(app):
    t = threading.Thread(target=scheduler_loop, args=(app,), daemon=True)
    t.start()
    app.logger.info('Scheduler started')

