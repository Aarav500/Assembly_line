Full-text search integration scaffold for Flask with Elasticsearch or Meilisearch.

Quickstart:
- Copy .env.example to .env and adjust settings.
- Option A: Local
  - python -m venv .venv && source .venv/bin/activate
  - pip install -r requirements.txt
  - export FLASK_APP=wsgi.py
  - flask --app wsgi.py run
- Option B: Docker Compose
  - docker compose up --build

Use the API:
- Initialize index: POST http://localhost:5000/api/indexes/documents/init
- Bulk sample via CLI: docker compose exec app flask search-reindex-sample documents --count 20
- Search: GET http://localhost:5000/api/indexes/documents/search?q=sample

Switch backend by setting SEARCH_BACKEND to elasticsearch or meilisearch.

