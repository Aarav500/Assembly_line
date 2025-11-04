import os
import threading
import traceback
from datetime import datetime
from typing import Optional

from training.trainer import run_causal_lm_training


class TrainingRunner:
    def __init__(self, job_manager, datasets, base_output_dir: str, logs_dir: str):
        self.job_manager = job_manager
        self.datasets = datasets
        self.base_output_dir = base_output_dir
        self.logs_dir = logs_dir
        os.makedirs(self.base_output_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

    def _job_output_dir(self, job_id: str) -> str:
        return os.path.join(self.base_output_dir, 'jobs', job_id)

    def _job_log_path(self, job_id: str) -> str:
        return os.path.join(self.logs_dir, f'job_{job_id}.log')

    def run_async(self, job_id: str):
        t = threading.Thread(target=self._run, args=(job_id,), daemon=True)
        t.start()

    def _run(self, job_id: str):
        job = self.job_manager.get_job(job_id)
        if not job:
            return
        out_dir = self._job_output_dir(job_id)
        os.makedirs(out_dir, exist_ok=True)
        self.job_manager.set_running(job_id, out_dir)
        log_path = self._job_log_path(job_id)
        with open(log_path, 'a', encoding='utf-8') as logf:
            def log(msg: str):
                ts = datetime.utcnow().isoformat() + 'Z'
                line = f"[{ts}] {msg}\n"
                logf.write(line)
                logf.flush()
            try:
                log('Starting training job')
                cancel_event = self.job_manager.cancel_event(job_id)
                run_causal_lm_training(config=job['config'], output_dir=out_dir, log_fn=log, cancel_event=cancel_event)
                if cancel_event and cancel_event.is_set():
                    log('Job canceled by user')
                    # status already set to canceled by job_manager
                else:
                    log('Training completed successfully')
                    self.job_manager.set_done(job_id)
            except Exception as e:
                tb = traceback.format_exc()
                log(f"Training failed: {e}\n{tb}")
                self.job_manager.set_failed(job_id, str(e))

    def get_job_logs(self, job_id: str) -> Optional[str]:
        if not self.job_manager.get_job(job_id):
            return None
        log_path = self._job_log_path(job_id)
        if not os.path.isfile(log_path):
            return ""
        with open(log_path, 'r', encoding='utf-8') as f:
            return f.read()

