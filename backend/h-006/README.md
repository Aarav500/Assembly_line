# Versioned Knowledge Snapshots (Time-Travel Queries)

This service provides versioned storage for knowledge items and supports time-travel queries to fetch the state of an item as-of a given timestamp or version number.

Stack: Python, Flask, SQLAlchemy (SQLite by default)

Quickstart

- python3 -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- FLASK_APP=app:app flask run

Environment

- DATABASE_URL: SQLAlchemy database URL (default sqlite:///data.db)

API

- POST /items
  Body: {"key":"topic-1","content":"...","author":"alice","timestamp":"2025-01-01T00:00:00Z"}
  Creates a new item if missing or appends a new version if the key exists.

- POST /items/{key}/versions
  Body: {"content":"...","author":"bob","timestamp":"2025-01-02T00:00:00Z"}
  Appends a new version for an existing item.

- GET /items/{key}?version=3
  Fetch a specific version.

- GET /items/{key}?as_of=2025-01-03T12:00:00Z
  Fetch the latest version at or before the given timestamp.

- GET /items/{key}/versions?limit=50&offset=0
  List versions for the item.

- GET /search?q=keyword&as_of=2025-01-03T12:00:00Z
  Search items by their as-of snapshot. Returns items whose content contains the substring (case-insensitive).

Notes

- Timestamps are stored as naive UTC datetimes internally; API returns ISO 8601 with Z.
- When creating a new version, the timestamp must be greater than or equal to the last version timestamp for that item.

