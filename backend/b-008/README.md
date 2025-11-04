Idea Ranking by Feasibility, Novelty, and Market Potential

Stack: Python, Flask

How to run:
- python3 -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- python app.py

Open http://localhost:8000 to use the UI, or POST to /api/rank with JSON:
{
  "ideas": [ { "title": "...", "description": "..." } ],
  "weights": { "feasibility": 0.34, "novelty": 0.33, "market": 0.33 }
}

Response contains sorted results with per-dimension scores and overall.
