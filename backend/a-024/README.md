Project-level token and cost forecast service

Stack: Python, Flask

Quick start:
- pip install -r requirements.txt
- python app.py
- GET http://localhost:8000/health
- GET http://localhost:8000/models
- POST http://localhost:8000/forecast with JSON body

Environment:
- PRICING_FILE: path to models pricing JSON (default: models.json)

Forecast request schema:
{
  "project": "my-project",
  "assumptions": {
    "overhead_tokens_per_call": 50
  },
  "runs": [
    {
      "model": "gpt-4o-mini",
      "count": 1000,
      "input": { "tokens": 300 },
      "output": { "tokens": 200 }
    },
    {
      "model": "gpt-4o",
      "count": 200,
      "input": { "words": 250 },
      "output": { "chars": 800 }
    }
  ]
}

Notes:
- Pricing in models.json is example data. Update with your vendor rates.
- Token estimation falls back to: tokens > chars (~4 chars/token) > words (~1.3 tokens/word).
- Costs are computed per 1,000,000 tokens using model-specific input/output rates.

