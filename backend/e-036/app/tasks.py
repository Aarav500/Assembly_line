import concurrent.futures
import threading
import uuid
from typing import Any, Callable, Dict


class TaskManager:
    def __init__(self, max_workers: int = 4) -> None:
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.lock = threading.Lock()
        self.jobs: Dict[str, dict] = {}

    def submit(self, fn: Callable, *args, **kwargs) -> str:
        job_id = str(uuid.uuid4())
        with self.lock:
            self.jobs[job_id] = {"status": "queued"}

        def _wrap():
            with self.lock:
                self.jobs[job_id] = {"status": "running"}
            try:
                result = fn(*args, **kwargs)
                with self.lock:
                    self.jobs[job_id] = {"status": "completed", "result": result}
            except Exception as e:  # noqa: BLE001
                with self.lock:
                    self.jobs[job_id] = {"status": "error", "error": str(e)}

        self.executor.submit(_wrap)
        return job_id

    def get(self, job_id: str) -> dict:
        with self.lock:
            return self.jobs.get(job_id, {"status": "unknown"})


task_manager = TaskManager()

