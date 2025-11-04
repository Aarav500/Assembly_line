Global plugin/connector system (Notion, Figma, Jira, Slack, S3, Databases)

Stack: Python + Flask

Quickstart
- Create and fill .env from .env.example
- pip install -r requirements.txt
- python src/app.py

API
- GET /health
- GET /api/connectors
- GET /api/{connector}/health
- GET /api/{connector}/search?q=...
- GET /api/{connector}/get?id=...
- POST /api/{connector}/action { "action": "...", "params": { ... } }

Supported actions
- notion: search, get, get_block_children(block_id)
- figma: search, get_file(file_key)
- jira: search (JQL), get (issue key)
- slack: search, post_message(channel, text, ...), list_channels(limit)
- s3: list_objects(prefix, max_keys), get_object(key, as_presigned_url, expires_in)
- database: list_tables(), select(query, params, limit), execute_raw_select(query, params) when ALLOW_DB_RAW_SELECT=true

Security notes
- Do not expose this service publicly without auth.
- Database connector only allows SELECT by default.

