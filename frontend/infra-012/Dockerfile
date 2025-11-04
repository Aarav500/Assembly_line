FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/usr/local/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app app
COPY scripts scripts
RUN chmod +x scripts/*.sh && mkdir -p /app/run

ENV CELERY_BROKER_URL=redis://redis:6379/0 \
    CELERY_RESULT_BACKEND=redis://redis:6379/1 \
    CELERY_TIMEZONE=UTC \
    CELERY_TASK_DEFAULT_QUEUE=default \
    LOG_LEVEL=INFO

CMD ["bash", "-lc", "celery -A app.celery_app:celery worker -l ${LOG_LEVEL}"]

