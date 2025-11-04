import os
from dotenv import load_dotenv

load_dotenv()

# Ensure tasks are imported so Celery can register them
from app.celery_app import celery_app  # noqa: E402,F401
import app.tasks.export_tasks  # noqa: E402,F401
import app.tasks.import_tasks  # noqa: E402,F401

# Note: Run the worker with: celery -A app.celery_app.celery_app worker -l info

