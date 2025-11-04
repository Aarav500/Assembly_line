import time
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import current_app
from .db import db
from .models import Environment, ProvisionTask
from .audit import log_event


class Provisioner:
    def __init__(self):
        self._executor = None
        self._app = None

    def init_app(self, app):
        self._app = app
        self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix='provisioner')

    def submit(self, fn, *args, **kwargs):
        if not self._executor:
            raise RuntimeError('Provisioner not initialized')
        return self._executor.submit(self._run_with_context, fn, *args, **kwargs)

    def _run_with_context(self, fn, *args, **kwargs):
        # Ensure app context is available in thread
        with self._app.app_context():
            return fn(*args, **kwargs)


provisioner = Provisioner()


def _append_log(task: ProvisionTask, line: str):
    logs = (task.logs or '') + (line + "\n")
    task.logs = logs


def start_provision(environment_id: str, actor: str = 'system'):
    env = Environment.query.get(environment_id)
    if not env:
        return
    task = ProvisionTask(environment_id=env.id, action='provision', status='running', logs='Starting provision...\n')
    db.session.add(task)
    env.status = 'provisioning'
    db.session.commit()

    try:
        delay = current_app.config.get('PROVISION_DELAY_SECONDS', 1.0)
        _append_log(task, f'Provisioning resources for {env.env_type}/{env.name}...')
        db.session.commit()
        time.sleep(delay)
        env.status = 'active'
        _append_log(task, 'Provision succeeded.')
        task.status = 'succeeded'
        db.session.commit()
        log_event(team_id=env.team_id, action='provision_succeeded', actor=actor, environment_id=env.id, details={'name': env.name})
    except Exception as e:
        env.status = 'failed'
        task.status = 'failed'
        _append_log(task, f'Provision failed: {e!r}')
        db.session.commit()
        log_event(team_id=env.team_id, action='provision_failed', actor=actor, environment_id=env.id, details={'error': str(e)})


def start_deprovision(environment_id: str, actor: str = 'system'):
    env = Environment.query.get(environment_id)
    if not env:
        return
    task = ProvisionTask(environment_id=env.id, action='deprovision', status='running', logs='Starting deprovision...\n')
    db.session.add(task)
    env.status = 'deprovisioning'
    db.session.commit()

    try:
        delay = current_app.config.get('DEPROVISION_DELAY_SECONDS', 0.5)
        _append_log(task, f'Deprovisioning resources for {env.env_type}/{env.name}...')
        db.session.commit()
        time.sleep(delay)
        env.status = 'deleted'
        _append_log(task, 'Deprovision succeeded.')
        task.status = 'succeeded'
        db.session.commit()
        log_event(team_id=env.team_id, action='deprovision_succeeded', actor=actor, environment_id=env.id, details={'name': env.name})
    except Exception as e:
        env.status = 'failed'
        task.status = 'failed'
        _append_log(task, f'Deprovision failed: {e!r}')
        db.session.commit()
        log_event(team_id=env.team_id, action='deprovision_failed', actor=actor, environment_id=env.id, details={'error': str(e)})

