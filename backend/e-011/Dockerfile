FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./

EXPOSE 8080
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app", "--workers", "2", "--threads", "4", "--timeout", "60"]

