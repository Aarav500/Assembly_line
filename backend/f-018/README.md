Automated SLA Tracking and SLO Compliance Reports

Quick start
- Install: pip install -r requirements.txt
- Run: python app.py

Key endpoints
- POST /services: Create a service and define SLO targets
- GET /services: List services
- POST /measurements: Ingest metric points (single or batch)
- POST /incidents: Record incidents (optional metadata)
- GET /reports/daily?date=YYYY-MM-DD: Daily SLO report for all services
- GET /reports/daily/<service_id>?date=YYYY-MM-DD: Daily SLO report for a service
- GET /reports/period/<service_id>?from=YYYY-MM-DD&to=YYYY-MM-DD: Aggregate SLO over period
- GET /reports/error-budget/<service_id>?from=YYYY-MM-DD&to=YYYY-MM-DD: Error budget and burn rate

Notes
- Timestamps must be ISO-8601. "Z" is supported, otherwise include timezone offset.
- Metrics:
  - availability: fraction of up measurements across the day
  - latency_p95: 95th percentile of latency_ms values
  - error_rate: total errors / total requests
- SLO targets per service: availability (0-1), latency p95 (ms), error_rate (0-1)
- A lightweight background scheduler generates missing daily reports once a minute for the previous day.

