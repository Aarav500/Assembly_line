# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY gunicorn.conf.py ./

ENV PORT=8000 \
    SERVICE_NAME=template-flask-service \
    ENVIRONMENT=dev \
    LOG_LEVEL=INFO \
    OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317 \
    OTEL_EXPORTER_OTLP_PROTOCOL=grpc \
    OTEL_TRACES_SAMPLER=parentbased_traceidratio \
    OTEL_TRACES_SAMPLER_ARG=1.0

EXPOSE 8000

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app.app:create_app()"]

