import threading
import uuid
import queue
from typing import Any, Callable, Dict, Optional


class TaskRunner:
    def __init__(self):
        self._queue: "queue.Queue" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def submit(self, func: Callable, *args, **kwargs) -> str:
        task_id = str(uuid.uuid4())
        with self._lock:
            self._tasks[task_id] = {'task_id': task_id, 'status': 'queued', 'result': None}
        self._queue.put((task_id, func, args, kwargs))
        return task_id

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._tasks.get(task_id)

    def _worker(self):
        while not self._stop_event.is_set():
            try:
                task_id, func, args, kwargs = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            # Update to running
            with self._lock:
                self._tasks[task_id]['status'] = 'running'
            try:
                result = func(*args, **kwargs)
                with self._lock:
                    self._tasks[task_id]['status'] = 'completed'
                    self._tasks[task_id]['result'] = result
            except Exception as e:
                with self._lock:
                    self._tasks[task_id]['status'] = 'failed'
                    self._tasks[task_id]['result'] = {'error': str(e)}
            finally:
                self._queue.task_done()

