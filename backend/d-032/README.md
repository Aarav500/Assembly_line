Canary analysis dashboards and decision logs stored in a Git-backed repository.

Quickstart
- python3 -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- ./run.sh

API
- POST /api/runs
  Example:
  curl -s localhost:5000/api/runs -H 'Content-Type: application/json' -d '{
    "service": "payments",
    "aggregate_score": 92.3,
    "thresholds": {"pass": 90, "warn": 75},
    "metrics": [
      {"name": "latency_p95_ms", "baseline": 220, "canary": 205, "score": 95.4, "status": "pass"},
      {"name": "error_rate_%", "baseline": 0.7, "canary": 0.9, "score": 72.0, "status": "warn"}
    ],
    "decision": {"result": "hold", "reason": "Error rate slightly elevated"},
    "metadata": {"build": "1.2.3", "region": "us-east-1"}
  }'

- POST /api/runs/<id>/decision
  Example:
  curl -s localhost:5000/api/runs/<id>/decision -H 'Content-Type: application/json' -d '{"user":"oncall","result":"promote","reason":"metrics stable"}'

The app writes to $REPO_PATH (default ./repo) and commits changes with Git if available.

