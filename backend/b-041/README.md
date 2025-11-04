Project: generate-elevator-pitch--2-min-pitch--1-page-summary-automat

Description
Generate an elevator pitch, a two-minute pitch, and a one-page summary automatically from a single project brief.

Stack
- Python
- Flask

Quickstart
1) Create and activate a virtual environment
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\\Scripts\\activate

2) Install dependencies
   pip install -r requirements.txt

3) Run the app
   python app.py
   Open http://localhost:5000 in your browser.

API
POST /api/generate
Content-Type: application/json
Body (minimum fields required: project_name, problem, solution)
{
  "project_name": "Acme AI",
  "problem": "Manual data labeling is slow and costly",
  "solution": "An AI-assisted labeling platform",
  "target_users": "ML teams at mid-market companies"
}

Response
{
  "elevator_pitch": "...",
  "two_min_pitch": "...",
  "one_pager": "...",
  "meta": { "word_counts": { ... } }
}

Notes
- The generator uses structured templates and light heuristics to keep lengths appropriate for each format.
- No external APIs required.

