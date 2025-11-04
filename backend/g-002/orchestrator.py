import threading
import multiprocessing as mp
import time
from typing import Dict, List

import config
import db
import storage
from autoscaler import desired_workers
from training import run_training, TrainingCancelled


class Orchestrator:
    def __init__(self):
        self.queue: mp.Queue = mp.Queue()
        self.workers: List[mp.Process] = []
        self.stop_event = threading.Event()
        self.scheduler_thread: threading.Thread = threading.Thread(target=self._schedule_loop, daemon=True)
        self.scaler_thread: threading.Thread = threading.Thread(target=self._scale_loop, daemon=True)

    def start(self):
        db.init_db()
        self.scheduler_thread.start()
        self.scaler_thread.start()

    def stop(self):
        self.stop_event.set()
        # Signal workers to stop
        self._scale_to(0)

    def join(self):
        self.scheduler_thread.join(timeout=2)
        self.scaler_thread.join(timeout=2)
        for p in self.workers:
            p.join(timeout=2)

    def _schedule_loop(self):
        while not self.stop_event.is_set():
            try:
                ready = db.find_jobs_ready()
                for job in ready:
                    job_id = job["id"]
                    # Mark queued and enqueue
                    db.mark_queued(job_id)
                    self.queue.put(job_id)
                time.sleep(config.QUEUE_POLL_INTERVAL_SEC)
            except Exception as e:
                print(f"[scheduler] error: {e}")
                time.sleep(1.0)

    def _scale_loop(self):
        while not self.stop_event.is_set():
            try:
                counts = db.count_backlog()
                target = desired_workers(counts.get("pending", 0), counts.get("queued", 0), counts.get("running", 0))
                self._scale_to(target)
                time.sleep(config.SCALE_INTERVAL_SEC)
            except Exception as e:
                print(f"[autoscaler] error: {e}")
                time.sleep(1.0)

    def _scale_to(self, target: int):
        current = len(self.workers)
        if target > current:
            for _ in range(target - current):
                p = mp.Process(target=_worker_main, args=(self.queue,), daemon=True)
                p.start()
                self.workers.append(p)
        elif target < current:
            # Send stop signals to extra workers
            for _ in range(current - target):
                self.queue.put(None)
            # Clean up any finished processes
            self.workers = [p for p in self.workers if p.is_alive()]


def _worker_main(queue: mp.Queue):
    while True:
        job_id = queue.get()
        if job_id is None:
            break
        try:
            _run_job(job_id)
        except Exception as e:
            print(f"[worker] unexpected error running job {job_id}: {e}")
            # Job status updating is handled inside _run_job
            continue


def _run_job(job_id: str):
    row = db.get_job(job_id)
    if not row:
        return

    # If cancel was requested before starting, mark canceled and return
    if row.get("status") == "cancel_requested":
        db.mark_job_canceled(job_id)
        return

    # Claim attempt and set running
    attempt_id, attempt_num = db.start_attempt(job_id)

    # Reload after state change
    row = db.get_job(job_id)
    params = {}
    try:
        if row.get("params"):
            try:
                import json as _json
                params = _json.loads(row["params"]) or {}
            except Exception:
                params = {}
        log_path = row.get("log_path")
        run_training(job_id, params, log_path)
        db.complete_attempt(attempt_id, "succeeded")
        db.mark_job_completed(job_id)
    except TrainingCancelled:
        db.complete_attempt(attempt_id, "canceled")
        # job already marked canceled in training
    except Exception as e:
        err = str(e)
        db.complete_attempt(attempt_id, "failed", err)
        db.mark_job_retrying(job_id, attempt_num, err)

