Business-metric linked alerts (revenue, conversion, signups)

Quick start:
- python3 -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- python app.py

API:
- POST /events {type: visit|signup|purchase, amount?, user_id?, timestamp?}
- GET /metrics?window_minutes=60
- POST /alert-rules {name, metric: revenue|conversion_rate|signups, comparator: gt|lt|gte|lte|eq|neq, threshold, window_minutes, cool_down_minutes?, is_active?, channels?}
- GET /alert-rules
- PATCH /alert-rules/:id (optional fields: name, is_active, channels, threshold, comparator, window_minutes, cool_down_minutes)
- POST /alerts/test
- GET /alerts

Channels examples:
- [{"type":"console"}]
- [{"type":"webhook","url":"https://example.com/webhook"}]

Env:
- DATABASE_URL (default sqlite:///app.db)
- ALERT_EVAL_INTERVAL_SECONDS (default 60)
- ALERT_WEBHOOK_TIMEOUT (default 4)
- DISABLE_SCHEDULER=1 to disable background evaluator

