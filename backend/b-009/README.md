Project: Automated SWOT analysis for each idea

Stack: Python, Flask

Features:
- Web UI to input idea title and description
- Automatic SWOT generation (rule-based offline by default)
- Optional OpenAI-powered SWOT when OPENAI_API_KEY is provided
- SQLite persistence with Flask SQLAlchemy
- REST API endpoints for programmatic use

Quick start:
1) Create and activate a virtual environment
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate

2) Install dependencies
   pip install -r requirements.txt

3) (Optional) Enable OpenAI
   cp .env.example .env
   export OPENAI_API_KEY=your_key_here
   # optional: export OPENAI_MODEL=gpt-4o-mini

4) Run the app
   python app.py

5) Open the UI
   http://localhost:5000/

API:
- POST /api/ideas
  Body: { "title": "...", "description": "...", "provider": "rule" | "openai" }
  Response: { id, title, description, created_at, swot: { strengths[], weaknesses[], opportunities[], threats[], provider } }

- GET /api/ideas -> list recent ideas
- GET /api/ideas/{id} -> get idea and SWOT
- POST /api/ideas/{id}/regenerate { provider }

Notes:
- If OpenAI credentials are not set or fail, the app automatically falls back to the rule-based SWOT.
- The rule-based generator uses heuristics and keywords to provide a reasonable baseline.

