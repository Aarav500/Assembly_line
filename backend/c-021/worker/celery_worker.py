from app import create_app
from app.celery_app import celery, init_celery

flask_app = create_app()
init_celery(celery, flask_app)

# This module exposes `celery` for the Celery CLI to discover

