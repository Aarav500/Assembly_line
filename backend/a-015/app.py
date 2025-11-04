import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
import time
import json
import shlex
import signal
import threading
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response, abort

app = Flask(__name__, static_folder='static', template_folder='templates')


class Task:
    def __init__(self, action: str, cmd_str: str | None):
        self.id = str(uuid.uuid4())
        self.action = action
        self.cmd_str = cmd_str
        self.status = 'pending'  # pending, running, success, error, cancelled
        self.started_at = None
        self.ended_at = None
        self.returncode = None
        self.logs: list[str] = []
        self._cond = threading.Condition()
        self._process: subprocess.Popen | None = None
        self._cancel_requested = False

    def to_dict(self, include_logs=False):
        d = {
            'id': self.id,
            'action': self.action,
            'cmd': self.cmd_str,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'returncode': self.returncode,
        }
        if include_logs:
            d['logs'] = self.logs
        return d

    def append_log(self, line: str):
        with self._cond:
            timestamp = datetime.utcnow().strftime('%H:%M:%S')
            self.logs.append(f"[{timestamp}] {line.rstrip()}\n")
            self._cond.notify_all()

    def set_status(self, status: str):
        with self._cond:
            self.status = status
            if status in ('running',):
                self.started_at = datetime.utcnow()
            if status in ('success', 'error', 'cancelled'):
                self.ended_at = datetime.utcnow()
            self._cond.notify_all()

    def wait_for_updates(self, last_index: int, timeout: float = 15.0):
        with self._cond:
            if len(self.logs) == last_index and self.status not in ('success', 'error', 'cancelled'):
                self._cond.wait(timeout=timeout)
            new_logs = self.logs[last_index:]
            return new_logs, len(self.logs), self.status

    def cancel(self):
        with self._cond:
            self._cancel_requested = True
            if self._process and self._process.poll() is None:
                try:
                    if os.name == 'nt':
                        self._process.terminate()
                    else:
                        os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                except Exception:
                    try:
                        self._process.terminate()
                    except Exception:
                        pass
            self._cond.notify_all()


class TaskManager:
    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def create_task(self, action: str, cmd_str: str | None) -> Task:
        task = Task(action, cmd_str)
        with self._lock:
            self._tasks[task.id] = task
        threading.Thread(target=self._run_task, args=(task,), daemon=True).start()
        return task

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def _run_task(self, task: Task):
        task.set_status('running')
        if not task.cmd_str:
            # Simulated run when no command configured
            label = 'CodeGen' if task.action == 'codegen' else 'Fixer'
            steps = 8 if task.action == 'codegen' else 6
            task.append_log(f"{label} started (simulation mode)")
            for i in range(1, steps + 1):
                if task._cancel_requested:
                    task.append_log(f"{label} cancelled by user")
                    task.set_status('cancelled')
                    return
                time.sleep(0.8)
                task.append_log(f"{label}: step {i}/{steps} in progress...")
            task.append_log(f"{label} completed successfully")
            task.returncode = 0
            task.set_status('success')
            return

        # Real subprocess execution
        try:
            task.append_log(f"Starting: {task.cmd_str}")
            if os.name == 'nt':
                # On Windows avoid process group specifics
                task._process = subprocess.Popen(
                    task.cmd_str,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
            else:
                task._process = subprocess.Popen(
                    task.cmd_str,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    preexec_fn=os.setsid,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )

            assert task._process.stdout is not None
            for line in iter(task._process.stdout.readline, ''):
                if task._cancel_requested:
                    task.append_log('Cancellation requested. Terminating process...')
                    try:
                        if os.name == 'nt':
                            task._process.terminate()
                        else:
                            os.killpg(os.getpgid(task._process.pid), signal.SIGTERM)
                    except Exception as e:
                        task.append_log(f"Termination error: {e}")
                    break
                if line:
                    task.append_log(line.rstrip('\n'))
            task._process.wait()
            task.returncode = task._process.returncode
            if task._cancel_requested:
                task.set_status('cancelled')
                return
            if task.returncode == 0:
                task.append_log('Process completed successfully')
                task.set_status('success')
            else:
                task.append_log(f"Process failed with return code {task.returncode}")
                task.set_status('error')
        except FileNotFoundError:
            task.append_log('Executable not found. Check configuration.')
            task.returncode = 127
            task.set_status('error')
        except Exception as e:
            task.append_log(f"Unexpected error: {e}")
            task.returncode = 1
            task.set_status('error')


tasks = TaskManager()


def get_command_for_action(action: str) -> str | None:
    if action == 'codegen':
        cmd = os.environ.get('CODEGEN_CMD', '').strip()
        return cmd or None
    if action == 'fixer':
        cmd = os.environ.get('FIXER_CMD', '').strip()
        return cmd or None
    return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/run', methods=['POST'])
def run_action():
    data = request.get_json(silent=True) or request.form
    action = (data.get('action') if data else None) or ''
    action = action.lower().strip()
    if action not in ('codegen', 'fixer'):
        return jsonify({'error': 'Invalid action. Use "codegen" or "fixer".'}), 400

    cmd = get_command_for_action(action)
    task = tasks.create_task(action, cmd)
    return jsonify({'task': task.to_dict(include_logs=False)}), 201


@app.route('/api/status/<task_id>', methods=['GET'])
def task_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify({'task': task.to_dict(include_logs=True)})


@app.route('/api/cancel/<task_id>', methods=['POST'])
def cancel_task(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if task.status in ('success', 'error', 'cancelled'):
        return jsonify({'task': task.to_dict()}), 200
    task.cancel()
    return jsonify({'task': task.to_dict()}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

@app.route('/ready')
def readiness_check():
    """Readiness check endpoint"""
    return {"status": "ready"}
