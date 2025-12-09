# ============================================
# Infrastructure Service - Monitoring & Health Dashboard
# Multi-VEnv Support + System Monitoring
# ============================================

FROM python:3.11-slim as base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ============================================
# System Dependencies + Docker CLI
# ============================================
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    git \
    wget \
    build-essential \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Install Python packages for monitoring
# ============================================
RUN pip install --upgrade pip setuptools wheel && \
    pip install \
    flask \
    gunicorn \
    psutil \
    docker \
    requests

# ============================================
# Copy smart venv manager
# ============================================
COPY smart_venv_manager.py /app/

# ============================================
# Copy all application code
# ============================================
COPY . /app/

# ============================================
# Create directories
# ============================================
RUN mkdir -p \
    /app/.venvs \
    /app/logs \
    /app/data

# ============================================
# Process modules
# ============================================
RUN echo "=== Processing infrastructure modules ===" && \
    python smart_venv_manager.py /app --process || \
    echo "Warning: VEnv processing completed with warnings"

# ============================================
# Dashboard app is provided in infrastructure/app.py
# (copied above with the rest of the source tree)
# ============================================

# ============================================
# Expose port
# ============================================
EXPOSE 8080

# ============================================
# Health check
# ============================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# ============================================
# Run
# ============================================
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app", "--workers", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]