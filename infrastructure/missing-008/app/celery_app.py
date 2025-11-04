import os
from celery import Celery


def make_celery() -> Celery:
    broker = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    app = Celery("data_tasks", broker=broker, backend=backend, include=[
        "app.tasks.export_tasks",
        "app.tasks.import_tasks",
    ])
    app.conf.update(
        task_track_started=True,
        result_expires=86400,
        worker_max_tasks_per_child=100,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
    )
    return app


celery_app = make_celery()

