import logging
import random
import time
from typing import Any, Dict

import requests
from requests.exceptions import RequestException, Timeout

from .celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(
    name="app.tasks.add",
    bind=True,
    autoretry_for=(RuntimeError,),
    retry_backoff=2,  # exponential backoff base
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def add(self, x: int, y: int) -> int:
    # Simulate transient failure 20% of the time
    if random.random() < 0.2:
        raise RuntimeError("Transient add error; will retry")
    result = x + y
    logger.info("add result=%s", result)
    return result


@celery.task(
    name="app.tasks.fetch_url",
    bind=True,
    autoretry_for=(Timeout,),
    retry_backoff=3,
    retry_jitter=True,
    retry_kwargs={"max_retries": 4},
)
def fetch_url(self, url: str, timeout: float = 5.0) -> Dict[str, Any]:
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return {
            "url": url,
            "status_code": resp.status_code,
            "length": len(resp.content),
        }
    except (Timeout,) as e:
        # Let autoretry handle Timeout
        raise e
    except RequestException as e:
        # Non-timeout HTTP errors: retry manually a couple times
        if self.request.retries < 2:
            countdown = 5 * (2 ** self.request.retries)
            logger.warning("HTTP error; retrying in %ss: %s", countdown, e)
            raise self.retry(exc=e, countdown=countdown, max_retries=5)
        logger.error("HTTP error (no more retries): %s", e)
        raise


@celery.task(
    name="app.tasks.important_task",
    bind=True,
)
def important_task(self, payload: Dict[str, Any]) -> str:
    try:
        # Simulate work
        time.sleep(1.0)
        if payload.get("should_fail"):
            raise ValueError("Important task failed deterministically")
        return "processed"
    except ValueError as e:
        # immediate fail (non-retriable)
        logger.exception("important_task failed: %s", e)
        raise
    except Exception as e:
        # Retriable error with capped backoff
        retries = self.request.retries
        countdown = min(60, 2 ** retries)
        logger.warning("important_task transient error; retry #%s in %ss", retries + 1, countdown)
        raise self.retry(exc=e, countdown=countdown, max_retries=6)


@celery.task(name="app.tasks.cleanup")
def cleanup() -> str:
    # Place for periodic cleanup logic: removing stale cache, pruning results, etc.
    logger.info("Running cleanup job")
    time.sleep(0.5)
    return "cleanup_ok"


@celery.task(name="app.tasks.heartbeat")
def heartbeat() -> str:
    logger.info("Heartbeat: worker alive")
    return "ok"

