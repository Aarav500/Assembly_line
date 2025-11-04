Searchable Knowledge Snippets API

Simple Flask service to store and search developer knowledge snippets. Designed to be consumed by an IDE plugin or any client.

Quick start:
- python -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- python app.py

Environment:
- SNIPPETS_DB: path to SQLite database (default: ./snippets.db)

Endpoints:
- GET /health
- GET /: API info
- POST /api/snippets: create snippet
- GET /api/snippets: list snippets with filters (?language=&project=&framework=&tag=&limit=&offset=&pinned=)
- GET /api/snippets/<id>: get one
- PUT /api/snippets/<id>: update fields
- DELETE /api/snippets/<id>: delete
- POST /api/snippets/bulk: insert many
- GET /api/snippets/search?q=&language=&project=&framework=&tag=&file_path=&symbol=&limit=&offset=: full-text search
- POST /api/suggestions: contextual suggestions for IDE (body: {file_path, language, symbol, selection, project, n})
- GET /api/tags: aggregate tags with counts

Snippet JSON model:
{
  "id": 1,
  "title": "How to create venv",
  "content": "python -m venv .venv",
  "tags": ["python", "env"],
  "language": "python",
  "framework": "flask",
  "source": "internal",
  "file_path": "backend/app.py",
  "symbol": "create_app",
  "project": "acme-api",
  "pinned": false,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}

Notes:
- Uses SQLite FTS5 for fast full-text search with Porter stemming.
- FTS index is updated manually by the API on insert/update/delete.
- Tags are stored as JSON array and filterable via /api/snippets and /api/snippets/search.

