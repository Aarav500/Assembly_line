import heapq
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import List

from processor.events import Event, EventProcessor


@dataclass(order=True)
class _Job:
    next_run_ts: float
    seq: int
    event: Event = field(compare=False)
    attempt: int = field(compare=False, default=0)


class RetryManager:
    def __init__(
        self,
        processor: EventProcessor,
        logger: logging.Logger,
        *,
        max_retries: int,
        backoff_base: float,
        backoff_factor: float,
        backoff_max: float,
        jitter: float,
    ) -> None:
        self.processor = processor
        self.logger = logger
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_factor = backoff_factor
        self.backoff_max = backoff_max
        self.jitter = jitter

        self._queue: List[_Job] = []
        self._cv = threading.Condition()
        self._seq = 0
        self._running = False
        self._thread = threading.Thread(target=self._worker, name="retry-worker", daemon=True)

    def start(self) -> None:
        with self._cv:
            if self._running:
                return
            self._running = True
            self._thread.start()
            self.logger.info("retry manager started")

    def stop(self, timeout: float = 5.0) -> None:
        with self._cv:
            self._running = False
            self._cv.notify_all()
        self._thread.join(timeout=timeout)
        self.logger.info("retry manager stopped")

    def enqueue_event(self, event: Event) -> None:
        with self._cv:
            job = _Job(next_run_ts=time.time(), seq=self._next_seq(), event=event, attempt=0)
            heapq.heappush(self._queue, job)
            self._cv.notify_all()
        self.logger.info(
            "event enqueued",
            extra={"event_id": event.id, "event_type": event.type},
        )

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _schedule_retry(self, job: _Job) -> None:
        delay = min(self.backoff_max, self.backoff_base * (self.backoff_factor ** job.attempt))
        delay += random.uniform(0, self.jitter)
        job.next_run_ts = time.time() + delay
        job.seq = self._next_seq()
        with self._cv:
            heapq.heappush(self._queue, job)
            self._cv.notify_all()
        self.logger.warning(
            "event scheduled for retry",
            extra={"event_id": job.event.id, "event_type": job.event.type},
        )

    def _worker(self) -> None:
        while True:
            with self._cv:
                while self._running and not self._queue:
                    self._cv.wait()
                if not self._running and not self._queue:
                    return
                now = time.time()
                job = self._queue[0]
                if job.next_run_ts > now:
                    self._cv.wait(timeout=job.next_run_ts - now)
                    continue
                heapq.heappop(self._queue)
            try:
                self.processor.process(job.event)
                self.logger.info(
                    "event processed",
                    extra={"event_id": job.event.id, "event_type": job.event.type},
                )
            except Exception:
                job.attempt += 1
                if job.attempt > self.max_retries:
                    self.logger.error(
                        "event failed permanently",
                        exc_info=True,
                        extra={"event_id": job.event.id, "event_type": job.event.type},
                    )
                else:
                    self.logger.warning(
                        "event processing failed; will retry",
                        exc_info=True,
                        extra={"event_id": job.event.id, "event_type": job.event.type},
                    )
                    self._schedule_retry(job)

