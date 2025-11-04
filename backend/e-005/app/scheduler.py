import threading
import time
from flask import current_app
from .models import Policy
from .policy_engine import PolicyEngine
from .registry import RegistryClient


_scheduler_thread = None


def _runner(app):
    with app.app_context():
        interval = app.config.get('SCHEDULE_INTERVAL_MINUTES', 60)
        while True:
            try:
                enabled_policies = Policy.query.filter_by(enabled=True).all()
                if enabled_policies:
                    client = RegistryClient(
                        base_url=app.config['REGISTRY_URL'],
                        username=app.config.get('REGISTRY_USERNAME'),
                        password=app.config.get('REGISTRY_PASSWORD'),
                        verify_ssl=app.config.get('REGISTRY_VERIFY_SSL', True),
                    )
                    engine = PolicyEngine(client)
                    for p in enabled_policies:
                        try:
                            engine.apply_policy(p, simulate=p.dry_run)
                        except Exception:
                            pass
                # sleep after run
            except Exception:
                pass
            time.sleep(max(1, int(interval) * 60))


def start_scheduler_if_enabled(app):
    global _scheduler_thread
    if not app.config.get('SCHEDULE_ENABLED', False):
        return
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_thread = threading.Thread(target=_runner, args=(app,), daemon=True)
    _scheduler_thread.start()

