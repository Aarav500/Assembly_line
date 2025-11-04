FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV HOST=0.0.0.0 \
    PORT=8080 \
    LOG_LEVEL=INFO \
    RECONCILE_SECONDS=30 \
    CONFIG_PATH=/app/config/policies.yaml

EXPOSE 8080

CMD ["python", "app.py"]

