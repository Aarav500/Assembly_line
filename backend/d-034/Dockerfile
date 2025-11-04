FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=wsgi.py \
    FLASK_ENV=production \
    DATABASE_URL=sqlite:///instance/app.db \
    AUTH_TOKEN=changeme

RUN mkdir -p instance

EXPOSE 8000

CMD ["python", "wsgi.py"]

