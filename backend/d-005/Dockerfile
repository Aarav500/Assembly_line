# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.12.6

FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/home/appuser/.local/bin:${PATH}"
WORKDIR /app
# Create non-root user
RUN adduser --disabled-password --gecos "" --home /home/appuser appuser && chown -R appuser:appuser /app
# Minimal OS deps for runtime
RUN --mount=type=cache,id=apt-cache,sharing=locked,target=/var/cache/apt \
    --mount=type=cache,id=apt-lib,sharing=locked,target=/var/lib/apt \
    apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates tzdata \
  && rm -rf /var/lib/apt/lists/*

FROM base AS builder
# Install build tools for compiling wheels
RUN --mount=type=cache,id=apt-cache,sharing=locked,target=/var/cache/apt \
    --mount=type=cache,id=apt-lib,sharing=locked,target=/var/lib/apt \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
  && rm -rf /var/lib/apt/lists/*
# Build wheelhouse from requirements for optimal caching
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel \
 && pip wheel --wheel-dir=/wheels -r requirements.txt

# Dev wheels (optional)
FROM builder AS builder-dev
COPY requirements-dev.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir=/wheels-dev -r requirements-dev.txt

FROM base AS runtime
ENV APP_ENV=production \
    GUNICORN_CMD_ARGS="--config gunicorn.conf.py"
# Install from prebuilt wheels (no network) for deterministic, fast builds
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-index --find-links=/wheels -r requirements.txt \
 && rm -rf /wheels
# Copy application
COPY app app
COPY gunicorn.conf.py .
COPY wsgi.py .
USER appuser
EXPOSE 8000
CMD ["gunicorn", "wsgi:app"]

# Dev image with hot reload
FROM base AS dev
ENV APP_ENV=development \
    FLASK_APP=wsgi.py \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=8000
# Install runtime deps first
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-index --find-links=/wheels -r requirements.txt
# Install dev deps
COPY --from=builder-dev /wheels-dev /wheels-dev
COPY requirements-dev.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-index --find-links=/wheels-dev -r requirements-dev.txt \
 && rm -rf /wheels /wheels-dev
# Copy source (overridden by volume in compose during dev)
COPY app app
COPY wsgi.py .
USER appuser
EXPOSE 8000
CMD ["flask", "run", "--debug"]

