FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

# Create data directory for state persistence
RUN mkdir -p /data && chown -R 1000:1000 /data

ENV FLASK_ENV=production \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

CMD ["python", "-m", "app.server"]

