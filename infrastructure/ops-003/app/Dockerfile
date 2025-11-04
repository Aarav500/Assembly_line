FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py /app/

EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app", "--threads", "4", "--workers", "2", "--timeout", "60"]

