from prometheus_client import Counter, Histogram, Gauge, Info

# Basic app info
APP_INFO = Info("app_info", "Application info")

# Total inference requests, labeled by endpoint and status
INFERENCE_REQUESTS = Counter(
    "inference_requests_total",
    "Total number of inference requests",
    ["endpoint", "status"],
)

# Latency of inference requests by endpoint
INFERENCE_LATENCY = Histogram(
    "inference_request_latency_seconds",
    "Latency of model inference requests",
    ["endpoint"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ),
)

# Token throughput (input/output). Prometheus can compute rates over this counter.
TOKENS_PROCESSED = Counter(
    "inference_tokens_total",
    "Total number of tokens processed",
    ["type"],  # input|output
)

# Hallucination metrics. Score in [0,1]; higher is better (less hallucination)
HALLUCINATION_SCORE = Histogram(
    "hallucination_score",
    "Distribution of hallucination similarity scores (0=low, 1=high)",
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

HALLUCINATION_EVENTS = Counter(
    "hallucination_events_total",
    "Total number of flagged hallucination events",
    ["reason"],  # e.g., low_similarity, scoring_error
)

# Optional: service liveness/health gauge (set externally if desired)
SERVICE_UP = Gauge("service_up", "Service availability/liveness gauge")
SERVICE_UP.set(1)

