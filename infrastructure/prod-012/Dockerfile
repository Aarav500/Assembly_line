FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    APP_NAME=metrics-exporter-prometheus-custom-business-metrics \
    ENVIRONMENT=prod \
    SERVICE_VERSION=1.0.0 \
    ENABLE_SIMULATOR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8000", "app:app"]

