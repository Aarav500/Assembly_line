import json
import os
import random
import time
import hashlib
from datetime import datetime

import redis
from celery import Task
from celery.utils.log import get_task_logger

from .celery_app import celery_app
from . import config

logger = get_task_logger(__name__)

# Exceptions used to control retry/drain behavior
class TransientError(Exception):
    """Temporary failure that should be retried."""


class NonRetriableError(Exception):
    """Permanent failure that should go straight to DLQ."""


# Redis client for DLQ bookkeeping
_redis = redis.from_url(config.REDIS_URL)


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _failure_key(task_name: str, args, kwargs) -> str:
    """Compute a deterministic key representing the logical job for DLQ attempts."""
    try:
        args_json = json.dumps(args, sort_keys=True, default=str)
        kwargs_json = json.dumps(kwargs, sort_keys=True, default=str)
    except Exception:
        # Fallback non-deterministic key
        args_json = str(args)
        kwargs_json = str(kwargs)
    raw = f"{task_name}|{args_json}|{kwargs_json}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _send_to_dlq(payload: dict) -> None:
    # Ensure light-weight and JSON serializable payload
    try:
        # Push an audit record to Redis list for observability
        _redis.lpush("dlq:audit", json.dumps(payload))
    except Exception as e:
        logger.warning("Failed to push DLQ audit record: %s", e)

    # Enqueue DLQ handler task
    celery_app.send_task(
        name="app.tasks.dlq_handle_failed_task",
        kwargs={"payload": payload},
        queue=config.DLQ_QUEUE,
        serializer="json",
    )


class DLQTask(Task):
    """Base task that pushes unhandled failures to DLQ when retries are exhausted.

    Behavior:
    - If exception is NonRetriableError -> send to DLQ immediately.
    - Else if retries are exhausted -> send to DLQ.
    """

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # noqa: N802 (celery API)
        try:
            retries = getattr(self.request, "retries", 0) or 0
            max_retries = getattr(self, "max_retries", config.TASK_DEFAULT_MAX_RETRIES)
            exhausted = retries >= max_retries
            exc_type = type(exc).__name__

            should_dlq = isinstance(exc, NonRetriableError) or exhausted

            logger.error(
                "Task failure: %s task_id=%s retries=%s/%s exc_type=%s exhausted=%s",
                self.name,
                task_id,
                retries,
                max_retries,
                exc_type,
                exhausted,
            )

            if should_dlq:
                payload = {
                    "failed_at": _now_iso(),
                    "task_id": task_id,
                    "original_task": self.name,
                    "args": list(args),
                    "kwargs": dict(kwargs or {}),
                    "exception_type": exc_type,
                    "exception_message": str(exc),
                    "retries": retries,
                    "max_retries": max_retries,
                    "hostname": getattr(self.request, "hostname", None),
                }
                _send_to_dlq(payload)
        except Exception as e:
            logger.exception("Error during on_failure DLQ handling: %s", e)


@celery_app.task(
    name="app.tasks.unreliable_task",
    base=DLQTask,
    bind=True,
    autoretry_for=(TransientError,),
    retry_backoff=True,
    retry_backoff_max=config.TASK_RETRY_BACKOFF_MAX,
    retry_jitter=True,
    retry_kwargs={"max_retries": config.TASK_DEFAULT_MAX_RETRIES},
)
def unreliable_task(self, x: int, fail_ratio: float = 0.5, hard_fail_ratio: float = 0.1) -> int:
    """A sample task that randomly fails to demonstrate retries and DLQ.

    Args:
      x: input number
      fail_ratio: probability of transient failure that should be retried
      hard_fail_ratio: probability of non-retriable failure that goes to DLQ
    Returns:
      int: x * 2
    """
    r = random.random()
    logger.info("Processing unreliable_task x=%s r=%.3f", x, r)

    # Simulate work
    time.sleep(0.1)

    if r < hard_fail_ratio:
        # Permanent failure
        raise NonRetriableError(f"Hard failure processing x={x}")

    if r < fail_ratio:
        # Transient failure
        raise TransientError(f"Transient failure processing x={x}")

    return x * 2


@celery_app.task(
    name="app.tasks.dlq_handle_failed_task",
    bind=True,
)
def dlq_handle_failed_task(self, payload: dict) -> None:
    """Process dead-lettered tasks and attempt recovery.

    Policy:
    - If exception_type is TransientError and attempts < DLQ_MAX_RECOVERY_ATTEMPTS:
        Re-queue the original task with exponential backoff.
    - Else: park the message in Redis for manual inspection.
    """
    # Normalize payload
    original_task = payload.get("original_task")
    args = payload.get("args", [])
    kwargs = payload.get("kwargs", {})
    exc_type = payload.get("exception_type", "")

    key = _failure_key(original_task, args, kwargs)
    attempts_key = f"dlq:attempts:{key}"

    try:
        attempts = int(_redis.incr(attempts_key)) - 1  # return previous attempts count
    except Exception:
        attempts = 0

    logger.warning(
        "DLQ handling original_task=%s attempts=%s exc_type=%s payload_task_id=%s",
        original_task,
        attempts,
        exc_type,
        payload.get("task_id"),
    )

    try:
        # Recovery decision
        if exc_type == "TransientError" and attempts < config.DLQ_MAX_RECOVERY_ATTEMPTS:
            # Exponential backoff
            delay = int(
                min(
                    config.DLQ_RECOVERY_BACKOFF_SECONDS
                    * (config.DLQ_RECOVERY_BACKOFF_FACTOR ** attempts),
                    config.DLQ_RECOVERY_BACKOFF_MAX,
                )
            )

            logger.info(
                "Re-queuing task %s with delay=%ss (attempt %s/%s)",
                original_task,
                delay,
                attempts + 1,
                config.DLQ_MAX_RECOVERY_ATTEMPTS,
            )

            # Rebuild and enqueue the original task
            celery_app.send_task(
                name=original_task,
                args=args,
                kwargs=kwargs,
                countdown=delay,
                queue=config.DEFAULT_QUEUE,
                serializer="json",
            )
        else:
            # Park the message for manual inspection
            record = {
                **payload,
                "dlq_attempts": attempts,
                "parked_at": _now_iso(),
                "park_reason": (
                    "max_recovery_attempts_exceeded"
                    if exc_type == "TransientError"
                    else "non_retriable_error"
                ),
            }
            try:
                _redis.lpush("dlq:parked", json.dumps(record))
            except Exception as e:
                logger.error("Failed to park DLQ record: %s", e)
            finally:
                # Cleanup attempts counter
                try:
                    _redis.delete(attempts_key)
                except Exception:
                    pass
            logger.error(
                "Parked DLQ message for task %s after attempts=%s exc_type=%s",
                original_task,
                attempts,
                exc_type,
            )
    except Exception as e:
        logger.exception("Error in DLQ handler: %s", e)

