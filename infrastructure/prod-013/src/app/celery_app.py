from celery import Celery
from kombu import Queue
from . import config

celery_app = Celery("distributed_task_queue")
celery_app.config_from_object(config.CELERY_CONFIG)

# Define queues explicitly (Redis broker uses list keys for each queue)
celery_app.conf.task_queues = (
    Queue(config.DEFAULT_QUEUE),
    Queue(config.DLQ_QUEUE),
)

# Route tasks to queues
celery_app.conf.task_routes = {
    "app.tasks.unreliable_task": {"queue": config.DEFAULT_QUEUE},
    "app.tasks.dlq_handle_failed_task": {"queue": config.DLQ_QUEUE},
}

# Optional: Name workers with hostname pattern when launched via CLI

# Ensure modules are imported so tasks are registered
celery_app.autodiscover_tasks(["app"])  # tasks.py inside app will be discovered

