import os
import json
import threading
import uuid
from datetime import datetime
from typing import Dict, Optional


class JobManager:
    def __init__(self, state_path: str):
        self.state_path = state_path
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict] = {}
        self._cancel_events: Dict[str, threading.Event] = {}
        self._load_state()

    def create_job(self, config: Dict) -> str:
        with self._lock:
            job_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat() + 'Z'
            job = {
                'id': job_id,
                'created_at': now,
                'updated_at': now,
                'status': 'queued',
                'config': config,
                'output_dir': None,
                'error': None
            }
            self._jobs[job_id] = job
            self._cancel_events[job_id] = threading.Event()
            self._save_state()
            return job_id

    def set_running(self, job_id: str, output_dir: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job['status'] = 'running'
                job['updated_at'] = datetime.utcnow().isoformat() + 'Z'
                job['output_dir'] = output_dir
                self._save_state()

    def set_done(self, job_id: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job['status'] = 'completed'
                job['updated_at'] = datetime.utcnow().isoformat() + 'Z'
                self._save_state()

    def set_failed(self, job_id: str, error: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job['status'] = 'failed'
                job['updated_at'] = datetime.utcnow().isoformat() + 'Z'
                job['error'] = error
                self._save_state()

    def list_jobs(self):
        with self._lock:
            return list(self._jobs.values())

    def get_job(self, job_id: str) -> Optional[Dict]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            if self._jobs[job_id]['status'] in ('completed', 'failed', 'canceled'):
                return False
            self._cancel_events[job_id].set()
            self._jobs[job_id]['status'] = 'canceled'
            self._jobs[job_id]['updated_at'] = datetime.utcnow().isoformat() + 'Z'
            self._save_state()
            return True

    def cancel_event(self, job_id: str) -> Optional[threading.Event]:
        with self._lock:
            return self._cancel_events.get(job_id)

    def _save_state(self):
        tmp = self.state_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self._jobs, f, indent=2)
        os.replace(tmp, self.state_path)

    def _load_state(self):
        if not os.path.isfile(self.state_path):
            return
        try:
            with open(self.state_path, 'r', encoding='utf-8') as f:
                self._jobs = json.load(f)
            # recreate events for existing jobs
            for jid in list(self._jobs.keys()):
                self._cancel_events[jid] = threading.Event()
        except Exception:
            self._jobs = {}
            self._cancel_events = {}

