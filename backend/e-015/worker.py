import logging
import threading
import time
from typing import Optional

from job_queue import JobQueue

logger = logging.getLogger("spot.worker")


class WorkerThread(threading.Thread):
    def __init__(
        self,
        job_queue: JobQueue,
        stop_event: threading.Event,
        drain_event: threading.Event,
        per_job_seconds: int = 10,
        heartbeat_interval: float = 1.0,
    ):
        super().__init__(name="Worker")
        self.queue = job_queue
        self.stop_event = stop_event
        self.drain_event = drain_event
        self.per_job_seconds = per_job_seconds
        self.heartbeat_interval = heartbeat_interval
        self._current_job_id: Optional[int] = None

    def run(self):
        logger.info("Worker started")
        try:
            while not self.stop_event.is_set():
                if self.drain_event.is_set() and self._current_job_id is None:
                    # Draining and no in-flight job: idle until exit
                    time.sleep(0.2)
                    continue

                if self._current_job_id is None and not self.drain_event.is_set():
                    job = self.queue.fetch_and_claim_next()
                    if job is None:
                        time.sleep(0.5)
                        continue
                    self._current_job_id = job["id"]
                    payload = job["payload"]
                    attempts = job["attempts"]
                    logger.info("Processing job id=%s attempts=%s payload=%s", self._current_job_id, attempts, str(payload)[:200])

                # Process current job
                if self._current_job_id is not None:
                    self._process_current_job()

        except Exception as e:
            logger.exception("Worker crashed: %s", e)
        finally:
            logger.info("Worker exiting")

    def _process_current_job(self):
        job_id = self._current_job_id
        try:
            # Simulate chunked work with heartbeats to show progress
            remaining = self.per_job_seconds
            while remaining > 0:
                if self.stop_event.is_set():
                    break
                time.sleep(min(self.heartbeat_interval, remaining))
                remaining -= self.heartbeat_interval
                self.queue.heartbeat(job_id)
            # Mark complete if not interrupted by stop
            self.queue.mark_done(job_id)
            logger.info("Job %s completed", job_id)
        except Exception as e:
            logger.exception("Job %s failed: %s", job_id, e)
            self.queue.mark_failed(job_id, str(e))
        finally:
            self._current_job_id = None

