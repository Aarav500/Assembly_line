# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for kubernetes client (openshift), boto3 none required; add curl for health
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py ./run.py

EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "app.app:create_app()"]

