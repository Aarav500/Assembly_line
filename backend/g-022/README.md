Versioned inference endpoints with traffic-splitting and A/B testability

Endpoints:
- POST /predict: traffic-splits between versions per configured weights. Sticky via cookie.
- POST /v1/predict: force v1.
- POST /v2/predict: force v2.
- GET /splits: view current split and experiment id.
- GET /healthz: health check.

Request body:
- JSON: { "input": "text" } or { "text": "text" }
- Optional: user_id for deterministic assignment.

A/B override (for testing):
- Enable by setting env ALLOW_VARIANT_OVERRIDE=true
- Then use query ?variant=v1 or header X-Variant: v1

Sticky assignment:
- Cookie name: ab_variant
- Max age: 30 days (configurable)

Environment variables:
- TRAFFIC_SPLIT: e.g., "v1:0.7,v2:0.3" or JSON {"v1":0.6,"v2":0.4}
- EXPERIMENT_ID: experiment identifier used for deterministic hashing
- COOKIE_NAME: cookie name for variant
- COOKIE_TTL_SECONDS: cookie lifetime
- ALLOW_VARIANT_OVERRIDE: true/false
- LOG_DIR: directory for metrics logs (default logs)

Run locally:
- pip install -r requirements.txt
- python app.py
- curl -X POST localhost:8000/predict -H 'Content-Type: application/json' -d '{"input":"hello"}'

Docker:
- docker build -t ab-infer .
- docker run -p 8000:8000 -e TRAFFIC_SPLIT="v1:0.5,v2:0.5" ab-infer

Metrics:
- JSON lines written to logs/metrics.log

