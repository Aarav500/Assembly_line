import os
import shlex
import subprocess
import time
import requests
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import current_app
from ..models import db, Runbook, Drill, Snapshot, SnapshotSchedule
from .snapshots import restore_snapshot


STEP_TYPES = {
    'restore_latest_snapshot',
    'run_command',
    'http_check',
    'wait',
}


def drill_job(runbook_id: Optional[int] = None, drill_schedule_id: Optional[int] = None, drill_id: Optional[int] = None):
    from flask import current_app
    with current_app.app_context():
        if drill_id:
            drill = Drill.query.get(drill_id)
            if not drill:
                return
            runbook = Runbook.query.get(drill.runbook_id)
        else:
            runbook = Runbook.query.get(runbook_id)
            drill = Drill(runbook_id=runbook.id, status='PENDING')
            db.session.add(drill)
            db.session.commit()

        drill.started_at = datetime.utcnow()
        drill.status = 'RUNNING'
        drill.log_text = (drill.log_text or '') + f"Starting drill for runbook {runbook.id} at {drill.started_at.isoformat()}\n"
        db.session.commit()

        success = True
        step_results = []
        for idx, step in enumerate(runbook.steps_json or []):
            stype = step.get('type')
            name = step.get('name') or f'step-{idx+1}'
            params = step.get('params', {})
            drill.log_text += f"Executing step {idx+1}: {stype} - {name}\n"
            db.session.commit()
            try:
                result = _execute_step(stype, params)
                step_results.append({'step': idx+1, 'type': stype, 'name': name, 'result': result})
                drill.log_text += f"Step {idx+1} succeeded: {result}\n"
                db.session.commit()
            except Exception as e:
                success = False
                drill.log_text += f"Step {idx+1} failed: {e}\n{traceback.format_exc()}\n"
                db.session.commit()
                break

        drill.finished_at = datetime.utcnow()
        drill.status = 'SUCCESS' if success else 'FAILED'
        drill.result_json = {'steps': step_results, 'success': success}
        drill.log_text += f"Drill finished at {drill.finished_at.isoformat()} with status {drill.status}\n"
        db.session.commit()


def _execute_step(stype: str, params: Dict[str, Any]):
    if stype not in STEP_TYPES:
        raise ValueError(f'Unsupported step type: {stype}')

    if stype == 'restore_latest_snapshot':
        schedule_id = params.get('schedule_id')
        restore_path = params.get('restore_path')
        if not schedule_id:
            raise ValueError('restore_latest_snapshot requires schedule_id')
        snap = Snapshot.query.filter_by(schedule_id=schedule_id, status='SUCCESS').order_by(Snapshot.created_at.desc()).first()
        if not snap:
            raise RuntimeError('No successful snapshot found')
        path = restore_snapshot(snap, restore_path)
        return {'restored_to': path}

    if stype == 'run_command':
        cmd = params.get('cmd')
        timeout = params.get('timeout', 120)
        if not cmd:
            raise ValueError('run_command requires cmd')
        shell = isinstance(cmd, str)
        if shell:
            exec_cmd = cmd
        else:
            exec_cmd = ' '.join([str(c) for c in cmd])
        try:
            p = subprocess.run(exec_cmd if shell else shlex.split(exec_cmd), shell=shell, capture_output=True, timeout=int(timeout), text=True)
            returncode = p.returncode
            if returncode != 0:
                raise RuntimeError(f'Command failed ({returncode}): {p.stderr.strip()}')
            return {'stdout': p.stdout.strip(), 'returncode': returncode}
        except subprocess.TimeoutExpired:
            raise RuntimeError('Command timed out')

    if stype == 'http_check':
        url = params.get('url')
        timeout = params.get('timeout', 10)
        expect_status = params.get('expect_status', 200)
        contains_text = params.get('contains_text')
        if not url:
            raise ValueError('http_check requires url')
        r = requests.get(url, timeout=float(timeout))
        if r.status_code != int(expect_status):
            raise RuntimeError(f'Unexpected status: {r.status_code}')
        if contains_text and contains_text not in r.text:
            raise RuntimeError('Expected text not found in response')
        return {'status': r.status_code}

    if stype == 'wait':
        seconds = float(params.get('seconds', 1))
        time.sleep(seconds)
        return {'slept': seconds}

    raise ValueError(f'Unknown step type: {stype}')

