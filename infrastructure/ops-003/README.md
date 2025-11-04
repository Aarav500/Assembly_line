# Alerting: PagerDuty + Slack Integration (Prometheus + Python)

This repo provides a complete alerting stack:
- Python demo service exporting Prometheus metrics
- Prometheus scraping targets and evaluating alert rules
- Alertmanager routing alerts to Slack and PagerDuty with team-based routing and escalation policies

Quickstart
1) Copy .env.example to .env and set your credentials
2) docker compose up -d
3) Generate some load: curl http://localhost:8000/work
4) Adjust error rate to trigger alerts: curl "http://localhost:8000/set_error_rate?rate=0.2"

Services
- Demo app: http://localhost:8000
- Prometheus: http://localhost:9090
- Alertmanager: http://localhost:9093
- Node Exporter: http://localhost:9100

Routing and Escalation
- Team-based routes (core, payments) with dedicated Slack channels and PagerDuty services
- Default routes when team is not matched
- Escalation via alert rules: Warning thresholds and Critical thresholds (e.g., error rate > 5% -> warning, > 10% -> critical)
- Inhibition: Critical suppresses Warning for same alertname/service/instance

Environment variables
- Slack: SLACK_WEBHOOK_URL, SLACK_CHANNEL, SLACK_CHANNEL_CORE, SLACK_CHANNEL_PAYMENTS
- PagerDuty: PD_ROUTING_KEY_DEFAULT, PD_ROUTING_KEY_CORE, PD_ROUTING_KEY_PAYMENTS

Notes
- Alertmanager uses environment variable expansion; docker-compose passes --config.expand-env
- Prometheus points to Alertmanager using ${ALERTMANAGER_HOST}
- Modify thresholds in prometheus/rules/app-alerts.yml as desired

