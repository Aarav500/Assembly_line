FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/root/.local/bin:$PATH

# Install system deps and tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg apt-transport-https \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Install Trivy
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor -o /etc/apt/keyrings/trivy.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb stable main" | tee /etc/apt/sources.list.d/trivy.list \
    && apt-get update && apt-get install -y --no-install-recommends trivy \
    && rm -rf /var/lib/apt/lists/*

# Install Snyk CLI via npm
RUN npm install -g snyk && snyk --version || true

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app
COPY run.py /app/run.py

EXPOSE 8080

# Environment variables
ENV TRIVY_PATH=trivy \
    SNYK_PATH=snyk \
    SCAN_TIMEOUT=900

# SNYK_TOKEN must be provided at runtime when using Snyk
# HEALTHCHECK
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD curl -fsS http://localhost:8080/healthz || exit 1

CMD ["python", "run.py"]

