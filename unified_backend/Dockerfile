FROM python:3.11-slim

WORKDIR /app

# Copy service registry
COPY service_registry.json /app/service_registry.json

# Copy all backend modules
COPY backend /app/backend
COPY frontend /app/frontend
COPY infrastructure /app/infrastructure

# Install unified backend
COPY unified_backend/requirements.txt /app/unified_backend/requirements.txt
WORKDIR /app/unified_backend
RUN pip install --no-cache-dir -r requirements.txt

COPY unified_backend/app.py /app/unified_backend/app.py

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
