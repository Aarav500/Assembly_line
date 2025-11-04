import os


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(',') if v.strip()]


class Config:
    DEBUG = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")

    # Comma-separated list of agent endpoints
    AGENT_ENDPOINTS = _split_csv(
        os.getenv(
            "AGENT_ENDPOINTS",
            "http://localhost:5000/agent/A/process,http://localhost:5000/agent/B/process",
        )
    )

    # Retry/Backoff settings
    RETRIES_PER_AGENT = int(os.getenv("RETRIES_PER_AGENT", "3"))
    BACKOFF_BASE = float(os.getenv("BACKOFF_BASE", "0.2"))  # seconds
    BACKOFF_FACTOR = float(os.getenv("BACKOFF_FACTOR", "2.0"))
    BACKOFF_MAX = float(os.getenv("BACKOFF_MAX", "5.0"))
    BACKOFF_JITTER = os.getenv("BACKOFF_JITTER", "full")  # full | equal | none

    # Request timeout per attempt in seconds
    REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "3.0"))

