Environmental & Ethical Impact Analyst (Privacy, Bias, Carbon)

Quickstart
- Install: python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
- Run: python app.py
- Visit: http://localhost:5000

API
POST /api/analyze
Content-Type: application/json
Body example:
{
  "idea_text": "AI-based hiring assistant that collects resumes, interviews via webcam, and ranks candidates.",
  "daily_users": 500,
  "requests_per_user": 3,
  "uses_ml": true,
  "model_size": "medium",
  "data_per_user_mb": 200,
  "retention_months": 12,
  "data_per_request_mb": 2,
  "pue": 1.4,
  "grid_intensity": "global", 
  "renewable_offset": 0.1,
  "user_base_multiplier": 3
}

Response contains privacy, bias, carbon analyses and an overall risk level.

