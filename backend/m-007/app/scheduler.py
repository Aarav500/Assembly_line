import threading
import time
from flask import current_app
from .models import db
from .services import analyze_all_tests_and_schedule, execute_pending_retests


class Scheduler:
    def __init__(self, app):
        self.app = app
        self._stop_event = threading.Event()
        self._threads = []

    def start(self):
        t1 = threading.Thread(target=self._analyzer_loop, name="flaky-analyzer", daemon=True)
        t1.start()
        self._threads.append(t1)

        if self.app.config.get('AUTO_EXECUTE_RETESTS', True):
            t2 = threading.Thread(target=self._executor_loop, name="retest-executor", daemon=True)
            t2.start()
            self._threads.append(t2)

    def stop(self):
        self._stop_event.set()
        # No join to avoid blocking teardown

    def _analyzer_loop(self):
        interval = self.app.config.get('ANALYZE_INTERVAL_SECONDS', 60)
        while not self._stop_event.is_set():
            try:
                with self.app.app_context():
                    analyze_all_tests_and_schedule()
                    db.session.remove()
            except Exception:
                # Swallow exceptions to keep loop alive
                pass
            finally:
                time.sleep(interval)

    def _executor_loop(self):
        interval = self.app.config.get('EXECUTE_RETESTS_INTERVAL_SECONDS', 30)
        while not self._stop_event.is_set():
            try:
                with self.app.app_context():
                    execute_pending_retests(limit=3)
                    db.session.remove()
            except Exception:
                pass
            finally:
                time.sleep(interval)

