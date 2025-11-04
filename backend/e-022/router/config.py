import os


def str_to_bool(v: str, default=False) -> bool:
    if v is None:
        return default
    return v.lower() in ["1", "true", "t", "yes", "y"]


class Config:
    def __init__(self) -> None:
        self.host = os.getenv("ROUTER_HOST", "0.0.0.0")
        self.port = int(os.getenv("ROUTER_PORT", "8080"))

        # Upstream services (Blue/Green)
        self.blue_url = os.getenv("BLUE_URL", "http://127.0.0.1:5001")
        self.green_url = os.getenv("GREEN_URL", "http://127.0.0.1:5002")

        # Orchestration defaults
        self.default_strategy = os.getenv("DEFAULT_STRATEGY", "blue_green")  # blue_green | canary
        self.default_active = os.getenv("DEFAULT_ACTIVE", "blue")  # blue | green
        self.default_blue_weight = int(os.getenv("DEFAULT_BLUE_WEIGHT", "100"))
        self.default_green_weight = int(os.getenv("DEFAULT_GREEN_WEIGHT", "0"))

        # Optional: protect orchestrator endpoints with a bearer token
        self.orch_token = os.getenv("ORCH_TOKEN")

        # Sticky sessions: hash a provided key to get consistent routing
        self.sticky_sessions = str_to_bool(os.getenv("STICKY_SESSIONS", "true"), default=True)

        # Health check path for upstreams
        self.health_path = os.getenv("UPSTREAM_HEALTH_PATH", "/health")

        # Timeout when proxying to upstreams (seconds)
        self.proxy_timeout = float(os.getenv("PROXY_TIMEOUT", "10"))

