Canary release of new model versions with canary metrics and automatic rollback.

How it works:
- Traffic is split between stable and canary versions by canary_weight (0..1).
- Per-version metrics (requests, error rate, latency percentiles) are collected in-memory.
- A background monitor compares canary vs thresholds and auto-rolls back if degraded.
- State persists in state.json.

Run locally:
- python3 -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- export PORT=8000
- python app.py

Or with gunicorn:
- ./run.sh

Endpoints:
- POST /predict {"text": "..."}
  Headers:
    X-User-Id: optional sticky routing key
    X-Force-Model-Version: force a model version (e.g., v1 or v2)
  Query:
    ?debug=1 include canary state and metrics snapshot

- GET /metrics -> per-version metrics and canary state
- GET /admin/status -> current canary/stable, weight, thresholds
- POST /admin/canary/weight {"weight": 0.25}
- POST /admin/canary/set {"version": "v2", "weight": 0.1}
- POST /admin/canary/promote
- POST /admin/canary/rollback
- POST /admin/thresholds {"min_requests": 100, "canary_error_rate_absolute_max": 0.15, "relative_error_rate_increase_pct_allowed": 40, "canary_latency_p95_ms_max": 700}
- POST /admin/canary/toggle_auto {"enabled": true}

Environment variables:
- STATE_PATH: override path to state.json
- MODEL_V2_ERROR_PROB: e.g., 0.05 to simulate canary error rate
- MODEL_V2_ADDED_LATENCY_MS: add ms latency to simulate regression

Rollout tips:
- Start with weight=0.05, monitor /metrics, increase gradually, then promote.
- Auto rollback triggers when thresholds are breached.

