FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STORAGE_ROOT=/app/storage \
    TMP_DIR=/app/tmp \
    CLAMAV_MODE=clamscan \
    MAX_CONTENT_LENGTH=12582912 \
    MAX_FILE_SIZE=10485760

# System deps: clamav scanner and libmagic for python-magic
RUN apt-get update && apt-get install -y --no-install-recommends \
    clamav \
    libmagic1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . /app

# Create storage and tmp dirs with safe permissions
RUN mkdir -p /app/storage /app/tmp && chmod 750 /app/storage /app/tmp

EXPOSE 8000

# Try to pre-load virus DB at build-time (non-fatal if it fails)
RUN freshclam || true

CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app", "--workers", "2", "--threads", "4", "--timeout", "60"]

