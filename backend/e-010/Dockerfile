# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    SERVICE_NAME=mesh-demo

WORKDIR /app

# System deps (if needed)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt /app/app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/app/requirements.txt

COPY app /app/app

EXPOSE 8080

# Healthcheck (optional)
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT}/healthz || exit 1

# Use gunicorn for production
CMD ["gunicorn", "-w", "2", "-k", "gthread", "-b", "0.0.0.0:8080", "app.app:app"]

