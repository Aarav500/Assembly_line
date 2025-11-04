# Queryable FAQ & Knowledge Base Generator

Generate a searchable knowledge base and auto-FAQ from project documentation and code comments.

Stack: Python + Flask

## Features
- Index project docs (Markdown, RST, TXT) and code comments (multiple languages).
- Extract Python docstrings (module, classes, functions).
- TF-IDF search over indexed content.
- Heuristic FAQ generation from documentation headings and docstrings.
- REST API to index, search, and retrieve FAQs.

## Endpoints
- POST /index
  - Form-data: `archive` (zip of your project) and optional `project_name`.
  - or JSON: `{ "path": "/absolute/path/to/project" , "project_name": "MyProj"}`
- GET /search?q=...&k=10
- GET /faq
- GET /kb
- POST /reset

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Index a project directory:

```bash
curl -X POST http://localhost:5000/index \
  -H 'Content-Type: application/json' \
  -d '{"path": "/absolute/path/to/your/project", "project_name": "My Project"}'
```

Search:

```bash
curl "http://localhost:5000/search?q=installation&k=5"
```

View FAQ:

```bash
curl http://localhost:5000/faq
```

## Notes
- Large files (>2MB) are skipped.
- Only common doc and code file extensions are indexed (see config.py).
- The index is saved to `data/index.joblib`; FAQs to `data/faq.json`.

