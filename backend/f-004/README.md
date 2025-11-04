Distributed tracing correlation across services and jobs (Python + Flask)

Overview:
- service-a: Receives a request, calls service-b via HTTP, and enqueues a background job with injected trace context.
- service-b: Processes HTTP requests; its spans are correlated with the caller via W3C TraceContext.
- worker: Consumes jobs from Redis, extracts the trace context from the job payload, and continues the trace for async processing. It also calls service-b to demonstrate cross-service tracing from an async job.
- OpenTelemetry Collector forwards spans to Jaeger.

Run locally with Docker:
1) docker compose up --build
2) Trigger a trace: curl http://localhost:5000/do-work
3) Open Jaeger UI: http://localhost:16686 and search for service-a, service-b, or job-worker to see end-to-end traces.

Without Docker (console exporter):
- Create a virtualenv, pip install -r requirements.txt
- Start Redis locally
- In three terminals:
  - python service_b/app.py
  - python worker/worker.py
  - python service_a/app.py
- Trigger: curl http://localhost:5000/do-work
- Spans will print to console.

Environment variables:
- SERVICE_B_URL: URL for service-b (default http://localhost:5001)
- REDIS_URL: Redis connection URL (default redis://localhost:6379/0)
- QUEUE_NAME: Redis list name for jobs (default jobs)
- TRACE_EXPORTER: console or otlp (default console)
- OTEL_EXPORTER_OTLP_ENDPOINT: e.g., otel-collector:4317 when using docker compose
- OTEL_EXPORTER_OTLP_PROTOCOL: grpc or http/protobuf (grpc in compose)

