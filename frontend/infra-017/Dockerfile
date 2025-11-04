FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY synonyms ./synonyms
ENV PYTHONPATH=/app
ENV ELASTIC_HOST=http://localhost:9200
ENV INDEX_NAME=products
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

