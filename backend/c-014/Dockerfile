# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd -u 10001 -m -s /bin/bash app

FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

FROM base AS runtime

ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY app/ ./app/

RUN chown -R app:app /app
USER app

EXPOSE 5000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "app.app:app"]

