Canary Deployment Orchestrator (Flask)

Overview
- A lightweight Flask service that orchestrates canary deployments using metrics-based promotion and automatic rollback.
- Pluggable traffic router (includes a FakeRouter for local testing). Integrate with your own router (e.g., service mesh, gateway, or Kubernetes) by implementing providers/base.py.

How it works
- Create a deployment via POST /deployments with strategy and policy.
- Send periodic metrics for the canary via POST /metrics.
- A background evaluator checks metrics every interval and either increases canary traffic, continues at the same weight, or rolls back.

Run locally
- Python 3.11+
- pip install -r requirements.txt
- python app.py

Docker
- docker build -t canary-orchestrator .
- docker run --rm -p 8000:8000 canary-orchestrator

API
- GET /health
- POST /deployments
  Example body:
  {
    "service_name": "checkout-api",
    "new_version": "v2.1.0",
    "baseline_version": "v2.0.3",
    "strategy": {"initial_weight": 5, "step_weight": 10, "interval_sec": 60, "max_steps": 10},
    "policy": {
      "max_error_rate": 0.01,
      "max_latency_p95_ms": 350,
      "min_availability": 0.995,
      "max_cpu_utilization": 0.8,
      "min_requests": 200,
      "min_samples": 3,
      "sample_window_sec": 60,
      "max_consecutive_failures": 1
    }
  }
- GET /deployments
- GET /deployments/{id}
- POST /deployments/{id}/cancel
- POST /metrics
  Example body:
  {
    "deployment_id": "UUID",
    "metrics": {
      "requests": 1000,
      "errors": 5,
      "latency_p95_ms": 280,
      "availability": 0.999,
      "cpu_utilization": 0.45
    }
  }

Extending
- Implement providers/base.py TrafficRouter with your platform (set_traffic_split, promote, rollback) and inject it into CanaryOrchestrator.

Notes
- Aggregation approximates p95 latency via mean of reported p95s per sample window.
- Error rate and availability are weighted by requests; CPU is a simple mean.
- Metrics sufficiency requires at least min_samples and min_requests within the sample_window_sec.

