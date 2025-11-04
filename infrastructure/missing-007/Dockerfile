FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV REDIS_URL=redis://redis:6379/0 \
    MESSAGE_QUEUE_URL=redis://redis:6379/0 \
    CORS_ALLOWED_ORIGINS=* \
    SECRET_KEY=please-change-me

CMD ["python", "run.py"]

