import threading
import queue
import uuid
import logging
from typing import Callable, Dict, Any

logger = logging.getLogger(__name__)

class JobWorker(threading.Thread):
    def __init__(self, q: queue.Queue, handler: Callable[[Dict[str, Any]], None], name: str):
        super().__init__(daemon=True, name=name)
        self.q = q
        self.handler = handler
        self._stop = threading.Event()

    def run(self):
        logger.info("Job worker %s started", self.name)
        while not self._stop.is_set():
            try:
                job = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self.handler(job)
            except Exception as e:
                logger.exception("Job handler error: %s", e)
            finally:
                self.q.task_done()

    def stop(self):
        self._stop.set()


def new_job_id() -> str:
    return str(uuid.uuid4())

