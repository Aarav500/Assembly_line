Project: Cost Anomaly Detection with Tagging-based Breakdowns

Stack: Python, Flask, SQLAlchemy, Pandas

Quick start:
- python3 -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- python app.py

Endpoints:
- GET /health
- POST /ingest
  Body: {"records": [{"date": "2025-01-01", "amount": 12.34, "tags": {"env": "prod", "service": "api"}}]}
- GET /breakdown?group_by=service&period=monthly&start=2025-01-01&end=2025-12-31
- GET /anomalies?group_by=service&method=zscore&threshold=3&period=daily&window=7&min_points=14&direction=both

Notes:
- group_by is any key present in the record's tags. Missing keys aggregate into "__untagged__".
- period supports daily, weekly, monthly. Weekly uses ISO week starting Monday; monthly uses first-of-month.
- Anomaly methods: zscore (rolling mean/std), mad (rolling median/MAD). Missing periods are filled with 0 to keep series continuous.
- Configure database via DATABASE_URL (default sqlite:///data.db).
