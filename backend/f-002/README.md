Prebuilt Grafana dashboards per project with drill-downs

Overview
- Flask service that manages per-project Grafana folders and dashboards via Grafana HTTP API.
- Creates two dashboards per project: Overview and Detail.
- Panels include drill-down links from Overview to Detail and a back link from Detail to Overview.

Prerequisites
- Grafana instance reachable from this service
- Grafana API token with permissions to create folders and dashboards
- A metrics datasource in Grafana (default prometheus) and its UID

Setup
1) Create and export a Grafana API token (Server Admin or sufficient org privileges).
2) Find your datasource UID in Grafana (Settings -> Data sources -> your source -> UID).
3) Copy .env.sample to .env and fill values.

Install and run
- python3 -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- export $(grep -v '^#' .env | xargs)
- python app.py

API
- GET /healthz
- GET /api/projects
- POST /api/projects
  Body: {"name": "my-project", "createDashboards": true}
- POST /api/projects/<name>/dashboards/refresh
- DELETE /api/projects/<name>

Notes
- Dashboard JSON uses Prometheus-style queries. Adjust queries or set GRAFANA_DATASOURCE_TYPE/UID to match your environment.
- Folders and dashboards are created with deterministic UIDs, allowing idempotent updates and stable drill-down links.
- Deleting a project will attempt to delete dashboards first, then the folder.

