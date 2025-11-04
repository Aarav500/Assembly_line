# syntax=docker/dockerfile:1
FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive
ARG CONFTEST_VERSION=0.49.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates bash \
    && rm -rf /var/lib/apt/lists/*

# Install conftest
RUN set -eux; \
    arch=$(dpkg --print-architecture); \
    case "$arch" in \
      amd64)  ct_arch=x86_64 ;; \
      arm64)  ct_arch=arm64 ;; \
      armhf)  ct_arch=armv6 ;; \
      *) echo "Unsupported arch: $arch" && exit 1 ;; \
    esac; \
    curl -sSL -o /tmp/conftest.tar.gz \
      https://github.com/open-policy-agent/conftest/releases/download/v${CONFTEST_VERSION}/conftest_${CONFTEST_VERSION}_Linux_${ct_arch}.tar.gz; \
    tar -xzf /tmp/conftest.tar.gz -C /tmp; \
    mv /tmp/conftest /usr/local/bin/conftest; \
    chmod +x /usr/local/bin/conftest; \
    conftest --version

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV POLICY_DIR=/app/policies \
    PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "wsgi:app"]

