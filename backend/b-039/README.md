Idea Archival & Expiration Policies with Auto-Purge Options

Stack: Python + Flask + SQLAlchemy (SQLite by default)

Quickstart:
- python -m venv .venv && source .venv/bin/activate  (on Windows: .venv\\Scripts\\activate)
- pip install -r requirements.txt
- cp .env.example .env  (optional)
- python run.py

API Endpoints (prefix /api):
- GET  /health
- GET  /policies
- POST /policies {name, description?, auto_archive_after_days?, auto_purge_after_days?, purge_hard?, active?}
- GET  /policies/<id>
- PATCH /policies/<id>
- DELETE /policies/<id>

- GET  /ideas?status=active|archived|purged|all
- POST /ideas {title, content?, policy_id?, expires_at? (ISO), expires_in_days?, purge_hard_override?}
- GET  /ideas/<id>
- PATCH /ideas/<id> to update fields; or with {action: "archive"} or {action: "purge", hard?: true|false}
- DELETE /ideas/<id>?hard=true|false to purge

Notes:
- Status lifecycle: active -> archived -> purged. Purged can be soft (redacted) or hard (deleted).
- Background maintenance runs periodically (MAINTENANCE_INTERVAL_SECONDS) to auto-archive and auto-purge based on idea.expires_at or policy settings.
- Default policy named "default" is created automatically; customize or create additional policies and assign per idea.

