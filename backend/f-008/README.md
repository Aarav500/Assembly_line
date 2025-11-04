Auto-generated Incident Reports with LLM Summarization and RCA Draft

Quickstart
- Create and activate a Python 3.10+ virtual environment
- pip install -r requirements.txt
- cp .env.example .env and set OPENAI_API_KEY (or keep empty to use local fallback)
- python app.py
- Open http://localhost:5000

API
POST /api/report
- JSON body: { "raw_input": string, "context": string?, "severity": string? }
- Returns: { "incident": { ... } }

GET /api/report/:id
- Returns one incident

GET /api/reports
- Optional query params: severity, status

Notes
- Without OPENAI_API_KEY, a deterministic local fallback will generate a basic draft.
- SQLite database is created under instance/app.db by default.

