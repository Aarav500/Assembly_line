ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/home/appuser/.local/bin:$PATH"

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY wsgi.py ./

USER appuser

EXPOSE 8000
ENV FLASK_ENV=production

HEALTHCHECK --interval=30s --timeout=3s --retries=5 CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "wsgi:app"]

