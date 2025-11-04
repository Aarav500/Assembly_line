import time
import threading
import heapq
import uuid
import traceback
import random
import multiprocessing as mp
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, List, Tuple
from datetime import datetime, timezone

# Ensure a start method compatible with process-per-attempt timeout control
try:
    mp.set_start_method("fork")
except (RuntimeError, ValueError):
    # Fallback to default; on Windows this will be 'spawn'
    pass


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RetryPolicy:
    timeout_seconds: float = 30.0
    max_attempts: int = 3
    backoff_initial_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    backoff_max_seconds: Optional[float] = None
    jitter_seconds: float = 0.0

    def next_delay(self, attempt_number: int) -> float:
        # attempt_number is 1-based for the current attempt just finished
        base = self.backoff_initial_seconds * (self.backoff_multiplier ** (attempt_number - 1))
        if self.backoff_max_seconds is not None:
            base = min(base, self.backoff_max_seconds)
        jitter = 0.0
        if self.jitter_seconds and self.jitter_seconds > 0:
            jitter = random.uniform(0, self.jitter_seconds)
        return max(0.0, base + jitter)


@dataclass
class AttemptRecord:
    attempt: int
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    timed_out: bool = False
    success: bool = False
    error: Optional[str] = None
    traceback: Optional[str] = None


@dataclass
class Job:
    id: str
    task_name: str
    params: Dict[str, Any]
    policy: RetryPolicy
    status: str = "queued"  # queued | running | succeeded | failed | cancelled
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)
    next_run_ts: float = field(default_factory=lambda: time.time())
    attempt: int = 0
    result: Any = None
    error: Optional[str] = None
    history: List[AttemptRecord] = field(default_factory=list)
    cancel_requested: bool = False

    def to_dict(self, summary: bool = False) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "task": self.task_name,
            "params": self.params,
            "status": self.status,
            "attempt": self.attempt,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if not summary:
            d.update({
                "policy": asdict(self.policy),
                "result": self.result,
                "error": self.error,
                "history": [asdict(h) for h in self.history],
                "next_run_at": datetime.fromtimestamp(self.next_run_ts, tz=timezone.utc).isoformat() if self.next_run_ts else None,
                "cancel_requested": self.cancel_requested,
            })
        return d


class JobQueue:
    def __init__(self):
        self._lock = threading.RLock()
        self._cv = threading.Condition(self._lock)
        self._jobs: Dict[str, Job] = {}
        self._heap: List[Tuple[float, int, str]] = []  # (next_run_ts, seq, job_id)
        self._seq = 0

    def submit(self, task_name: str, params: Optional[Dict[str, Any]] = None, policy: Optional[Dict[str, Any]] = None) -> Job:
        from jobs import TASKS  # Ensure task exists at submit time
        if task_name not in TASKS:
            raise ValueError(f"Unknown task '{task_name}'")
        if params is None:
            params = {}
        rp = RetryPolicy(**policy) if policy else RetryPolicy()
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            task_name=task_name,
            params=params,
            policy=rp,
            next_run_ts=time.time(),
        )
        with self._cv:
            self._jobs[job_id] = job
            self._enqueue(job)
            self._cv.notify()
        return job

    def cancel(self, job_id: str) -> bool:
        with self._cv:
            job = self._jobs.get(job_id)
            if not job:
                return False
            if job.status in ("succeeded", "failed", "cancelled"):
                return True
            if job.status == "running":
                job.cancel_requested = True
                job.updated_at = utcnow_iso()
                # We don't attempt to terminate mid-attempt here; it will cancel after attempt completes
                return True
            # If queued, mark cancelled and it will not be executed
            job.status = "cancelled"
            job.updated_at = utcnow_iso()
            job.cancel_requested = True
            return True

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, status: Optional[str] = None) -> List[Job]:
        with self._lock:
            if status:
                return [j for j in self._jobs.values() if j.status == status]
            return list(self._jobs.values())

    def _enqueue(self, job: Job):
        self._seq += 1
        heapq.heappush(self._heap, (job.next_run_ts, self._seq, job.id))

    def _pop_ready_job(self) -> Tuple[Optional[Job], Optional[float]]:
        now = time.time()
        while self._heap:
            ts, _, jid = self._heap[0]
            if ts > now:
                # Not yet ready; return wait time
                return None, ts - now
            heapq.heappop(self._heap)
            j = self._jobs.get(jid)
            if not j:
                continue
            if j.status != "queued":
                # Skip stale entry
                continue
            # Found ready job
            return j, 0.0
        return None, None

    def _reschedule_or_finish(self, job: Job, success: bool, error: Optional[str], timed_out: bool):
        now = time.time()
        if success:
            job.status = "succeeded"
            job.error = None
            job.updated_at = utcnow_iso()
            return
        # Failure path
        job.error = error
        job.updated_at = utcnow_iso()
        if job.cancel_requested:
            job.status = "cancelled"
            return
        if job.attempt >= job.policy.max_attempts:
            job.status = "failed"
            return
        # schedule retry with exponential backoff
        delay = job.policy.next_delay(job.attempt)
        job.next_run_ts = now + delay
        job.status = "queued"
        self._enqueue(job)


class Worker(threading.Thread):
    def __init__(self, queue: JobQueue):
        super().__init__(daemon=True)
        self.queue = queue
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()
        with self.queue._cv:
            self.queue._cv.notify_all()

    def run(self):
        while not self._stop.is_set():
            with self.queue._cv:
                job, wait_time = self.queue._pop_ready_job()
                if not job:
                    # nothing ready; wait
                    if wait_time is None:
                        self.queue._cv.wait(timeout=0.5)
                    else:
                        self.queue._cv.wait(timeout=max(0.0, min(wait_time, 5.0)))
                    continue
                # Mark running
                job.status = "running"
                job.attempt += 1
                job.updated_at = utcnow_iso()
                attempt_rec = AttemptRecord(
                    attempt=job.attempt,
                    start_time=utcnow_iso(),
                )
                job.history.append(attempt_rec)
            # Execute outside lock
            success, result, error, tb, timed_out = self._execute_attempt(job)
            # Update job after execution
            with self.queue._cv:
                attempt_rec.end_time = utcnow_iso()
                attempt_rec.timed_out = timed_out
                attempt_rec.success = success
                if error:
                    attempt_rec.error = error
                if tb:
                    attempt_rec.traceback = tb
                if success:
                    job.result = result
                self.queue._reschedule_or_finish(job, success, error, timed_out)

    def _execute_attempt(self, job: Job):
        # Returns (success, result, error, traceback, timed_out)
        timeout = float(job.policy.timeout_seconds) if job.policy.timeout_seconds else None
        result_queue = mp.Queue()
        proc = mp.Process(target=_run_task, args=(job.task_name, job.params, result_queue), daemon=True)
        started = time.time()
        proc.start()
        timed_out = False
        success = False
        result = None
        error = None
        tb = None
        proc.join(timeout=timeout)
        if proc.is_alive():
            try:
                proc.terminate()
            except Exception:
                pass
            finally:
                proc.join()
            timed_out = True
            success = False
            error = f"Attempt timed out after {timeout} seconds"
            tb = None
            return success, result, error, tb, timed_out
        # Process finished within timeout; collect outcome
        try:
            # small timeout to ensure we read the message written by child
            outcome = result_queue.get(timeout=1.0)
        except Exception:
            outcome = None
        if not outcome:
            success = False
            error = "Task finished but no result reported"
            tb = None
            return success, result, error, tb, timed_out
        if outcome.get("ok"):
            success = True
            result = outcome.get("result")
            return success, result, None, None, timed_out
        else:
            success = False
            error = outcome.get("error")
            tb = outcome.get("traceback")
            return success, result, error, tb, timed_out


def _run_task(task_name: str, params: Dict[str, Any], result_queue: mp.Queue):
    try:
        from jobs import TASKS
        func = TASKS.get(task_name)
        if not func:
            raise ValueError(f"Unknown task '{task_name}'")
        res = func(**(params or {}))
        result_queue.put({"ok": True, "result": res})
    except Exception as e:
        tb = traceback.format_exc()
        result_queue.put({"ok": False, "error": str(e), "traceback": tb})

