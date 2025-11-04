Funding & Grant Matching Suggestions API

Stack: Python, Flask

Endpoints
- GET /health
- GET /api/opportunities
- POST /api/match

POST /api/match request body example:
{
  "name": "Acme AI",
  "sectors": ["ai", "saas"],
  "stage": "seed",
  "location": "north america",
  "amount_needed": 500000,
  "for_profit": true,
  "impact": false,
  "female_founder": false,
  "minority_owned": true,
  "university_affiliated": false,
  "climate": false,
  "tags": ["mlops", "data platform"],
  "description": "We build AI tooling for data teams.",
  "want_types": ["investor", "grant", "accelerator"]
}

Run
- python3 -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- python app.py

Config
- DATA_PATH: path to opportunities JSON (default: data/opportunities.json)

Notes
- Matching is rule-based with sector, stage, location, keyword (thesis/tags), and amount fit.
- Some opportunities have constraints (e.g., female founder, nonprofit-only) and deadlines.
- Scores are 0-100; higher means better fit.

