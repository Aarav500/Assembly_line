# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ARG VERSION="dev"
ARG GIT_SHA=""
ARG BUILD_DATE=""
ARG VCS_URL=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_VERSION=${VERSION} \
    GIT_SHA=${GIT_SHA} \
    BUILD_DATE=${BUILD_DATE} \
    VCS_URL=${VCS_URL} \
    SERVICE_NAME=image-signing-cosign-demo

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')" || exit 1

# OCI labels
LABEL org.opencontainers.image.title="Flask Cosign Demo" \
      org.opencontainers.image.description="Flask app signed with cosign (sigstore) on release" \
      org.opencontainers.image.source="${VCS_URL}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.licenses="Apache-2.0"

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "app.main:app"]

