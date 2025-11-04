FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Minimal runtime dependency for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy application source
COPY . /app

# Install dependencies (fallback to Flask + Gunicorn if no requirements.txt)
RUN python -m pip install --upgrade pip && \
    if [ -f requirements.txt ]; then pip install -r requirements.txt; else pip install "flask>=2" "gunicorn>=21"; fi

# Create unprivileged user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Default runtime env
ENV APP_MODULE=app:app \
    GUNICORN_WORKERS=2 \
    GUNICORN_BIND=0.0.0.0:8000 \
    GUNICORN_TIMEOUT=60 \
    GUNICORN_LOGLEVEL=info

EXPOSE 8000

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

CMD ["entrypoint.sh"]

