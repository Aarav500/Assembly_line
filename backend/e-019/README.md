Cross-Region Failover Scripts and DNS Failover Automation

This project provides a Flask API and Python scripts to automate cross-region failover and DNS updates. It supports Route53, Cloudflare, and a mock (no-op) provider for local testing.

Features
- Health checks for primary and secondary regions
- Manual failover/failback
- Automatic failover with optional auto-failback
- DNS record updates (A or CNAME) via providers
- API token authentication for HTTP endpoints
- State persisted to a JSON file
- Simulation endpoints/CLI for testing outages

Quick Start
1) Copy .env.example to .env and adjust values.
2) Build and run Docker:
   docker build -t failover:latest .
   docker run --env-file .env -p 8000:8000 -v $(pwd)/data:/data failover:latest
3) API Endpoints (use Authorization: Bearer <API_TOKEN>):
   GET  /health           -> liveness check
   GET  /status           -> current status and health
   POST /failover         -> automatic decision or with ?target=primary|secondary
   POST /failback         -> switch active to primary and update DNS
   POST /dns/sync         -> ensure DNS matches active region
   POST /simulate/outage  -> toggle outage simulation: JSON {"region": "primary|secondary", "down": true|false}

CLI
- Manual failover / status / monitor:
  python scripts/failover.py status
  python scripts/failover.py check
  python scripts/failover.py failover --to secondary
  python scripts/failover.py failback
  python scripts/failover.py dns-sync
  python scripts/failover.py simulate --region primary --down
  python scripts/health_monitor.py

Notes
- For Route53, ensure AWS credentials are available to the container via environment variables or IAM role.
- For Cloudflare, set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID.
- For local testing, use DNS_PROVIDER=mock.

