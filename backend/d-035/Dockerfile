FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config ./config

# Data directory for SQLite
RUN mkdir -p /app/data

EXPOSE 8080

ENV FLASK_HOST=0.0.0.0 \
    FLASK_PORT=8080 \
    TIMEZONE=UTC \
    SCHEDULE_CRON="0 3 * * *" \
    SCANNER=trivy

# Install trivy optionally at runtime in your environment or mount it into the container
# This image does not include trivy by default.

CMD ["python", "-m", "app.app"]

