FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy service registry
COPY service_registry.json /app/service_registry.json

# Copy all backend modules
COPY backend /app/backend
COPY frontend /app/frontend
COPY infrastructure /app/infrastructure

# Install unified backend dependencies
COPY unified_backend/requirements.txt /app/unified_backend/requirements.txt
WORKDIR /app/unified_backend
RUN pip install --no-cache-dir -r requirements.txt

# Copy the unified backend app
COPY unified_backend/app.py /app/unified_backend/app.py

EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]