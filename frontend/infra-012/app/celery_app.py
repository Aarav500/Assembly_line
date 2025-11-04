from celery import Celery
from kombu import Exchange, Queue
from .config import settings
from .beat_schedule import get_beat_schedule
from . import logging_config  # noqa: F401 - configure logging

celery = Celery(
    "background_jobs",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

celery.conf.update(
    enable_utc=True,
    timezone=settings.CELERY_TIMEZONE,
    task_default_queue=settings.CELERY_TASK_DEFAULT_QUEUE,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 3600},
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_send_task_events=True,
    task_send_sent_event=True,
    beat_schedule=get_beat_schedule(),
)

celery.conf.task_queues = (
    Queue("default", Exchange("default"), routing_key="default"),
    Queue("high", Exchange("high"), routing_key="high"),
    Queue("low", Exchange("low"), routing_key="low"),
)

celery.conf.task_routes = {
    "app.tasks.add": {"queue": "default"},
    "app.tasks.fetch_url": {"queue": "default"},
    "app.tasks.important_task": {"queue": "high"},
    "app.tasks.cleanup": {"queue": "low"},
    "app.tasks.heartbeat": {"queue": "low"},
}

from . import monitoring  # noqa: E402,F401 - register signal handlers

