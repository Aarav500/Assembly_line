import logging
import time
from typing import Dict
from celery import signals

logger = logging.getLogger("celery.monitor")
_start_times: Dict[str, float] = {}

@signals.task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    _start_times[task_id] = time.time()
    logger.info(
        "Task starting: name=%s id=%s args=%s kwargs=%s",
        getattr(task, "name", str(sender)), task_id, args, kwargs,
    )

@signals.task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **extra):
    started = _start_times.pop(task_id, None)
    duration_ms = int((time.time() - started) * 1000) if started else -1
    logger.info(
        "Task finished: name=%s id=%s state=%s duration_ms=%s",
        getattr(task, "name", str(sender)), task_id, state, duration_ms,
    )

@signals.task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **extra):
    logger.error(
        "Task failed: name=%s id=%s exc=%s",
        getattr(sender, "name", str(sender)), task_id, repr(exception),
        exc_info=einfo and einfo.exception,
    )

@signals.task_retry.connect
def task_retry_handler(request=None, reason=None, einfo=None, **kwargs):
    task_name = getattr(request, "task", "unknown")
    logger.warning(
        "Task retry scheduled: name=%s id=%s reason=%s retries=%s eta=%s",
        task_name, request.id, repr(reason), request.retries, getattr(request, "eta", None),
    )

