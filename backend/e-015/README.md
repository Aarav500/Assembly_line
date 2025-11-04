Spot instance strategies for cost savings & graceful interruptions (Flask)

Overview
- Demonstrates how to run stateless job processing on cost-effective EC2 Spot Instances while handling 2-minute interruption notices gracefully.
- Strategies implemented:
  - Draining mode: stop admitting new work as soon as an interruption signal is detected (IMDS or SIGTERM).
  - Finish in-flight job within a configurable grace window.
  - Health/readiness endpoints to allow rapid load balancer deregistration.
  - At-least-once processing by persisting a simple job queue in SQLite and re-queuing in-flight jobs on restart.
  - Optional simulation endpoints to test interruption logic.

Endpoints
- POST /jobs: enqueue a job with arbitrary JSON payload { ... }.
- GET /jobs/<id>: get status (queued, processing, done, failed).
- GET /health: liveness.
- GET /ready: readiness (503 when draining to trigger deregistration).
- GET /metrics: counts by job status and worker state.
- POST /simulate/interruption: trigger draining (set ALLOW_SIMULATE_INTERRUPTION=false to disable in prod).
- POST /drain: manual drain (e.g., used by Kubernetes preStop or an ASG lifecycle hook).
- POST /shutdown: force exit (for testing).

Environment variables
- DATABASE_URL: path to SQLite file (default: data/jobs.db)
- SPOT_WATCHER_ENABLED: true/false (default: true) — polls IMDS for spot interruptions.
- IMDS_URL: IMDS endpoint for spot interruptions (default: http://169.254.169.254/latest/meta-data/spot/instance-action)
- POLL_INTERVAL_SECONDS: IMDS poll interval (default: 5)
- GRACE_PERIOD_SECONDS: time before forced exit after draining (default: 110). Keep under 120s.
- JOB_PROCESSING_SECONDS: simulated seconds per job (default: 10)
- ALLOW_SIMULATE_INTERRUPTION: true/false (default: true)
- HOST/PORT: Flask bind host/port (default: 0.0.0.0:8080)

Run locally
- python -m venv .venv && source .venv/bin/activate
- pip install -r requirements.txt
- python app.py

Docker
- docker build -t spot-graceful .
- docker run --rm -p 8080:8080 -e ALLOW_SIMULATE_INTERRUPTION=true spot-graceful

AWS deployment notes
- Run in an Auto Scaling Group with Mixed Instances Policy using Spot to save costs.
- Ensure target group health checks call /ready; deregistration delay should be small (e.g., 10s) to react to draining.
- Use lifecycle hooks or instance refresh to drain via POST /drain before scale-in (optional).
- Ensure instance role allows IMDS access; IMDSv2 is used when available.
- Consider SQS/SNS or an external queue for production workloads; SQLite is for demo only.

Testing interruption
- curl -XPOST localhost:8080/simulate/interruption
- Observe /ready returns 503 and no new jobs are accepted; in-flight job completes before exit.

Caveats
- Use a single-process server; do not run multiple gunicorn workers with this in-process queue and worker.
- At-least-once semantics may reprocess jobs; make job handlers idempotent.

