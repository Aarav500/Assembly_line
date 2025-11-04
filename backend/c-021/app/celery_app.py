from celery import Celery
from datetime import timedelta

celery = Celery(__name__)


def init_celery(celery_app: Celery, flask_app):
    celery_app.conf.update(
        broker_url=flask_app.config["CELERY_BROKER_URL"],
        result_backend=flask_app.config["CELERY_RESULT_BACKEND"],
        task_default_queue=flask_app.config.get("CELERY_TASK_DEFAULT_QUEUE", "default"),
        task_always_eager=flask_app.config.get("CELERY_TASK_ALWAYS_EAGER", False),
        timezone=flask_app.config.get("CELERY_TIMEZONE", "UTC"),
        enable_utc=True,
        beat_schedule={
            # Example periodic task every 60s
            "celery-heartbeat": {
                "task": "app.tasks.celery_tasks.heartbeat",
                "schedule": timedelta(seconds=60),
                "options": {"queue": flask_app.config.get("CELERY_TASK_DEFAULT_QUEUE", "default")},
            }
        },
        imports=(
            "app.tasks.celery_tasks",
        ),
    )

    # Ensure tasks run within Flask app context
    TaskBase = celery_app.Task

    class AppContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery_app.Task = AppContextTask

    return celery_app

