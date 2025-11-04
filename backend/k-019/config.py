import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///metrics.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Default SLA targets (can be overridden per-agent)
    DEFAULT_SLA = {
        "target_uptime": 0.995,              # 99.5% uptime
        "max_error_rate": 0.02,              # <= 2% error rate
        "p95_latency_ms_target": 2000,       # P95 latency <= 2s
        "min_success_rate": 0.95,            # >= 95% success rate
        "max_cost_per_interaction_usd": None # optional cap
    }

    # Default metrics window if not specified in queries
    DEFAULT_WINDOW_DAYS = int(os.getenv("DEFAULT_WINDOW_DAYS", "30"))

