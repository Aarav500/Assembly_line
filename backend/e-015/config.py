import os
from dataclasses import dataclass


@dataclass
class Config:
    DATABASE_URL: str
    SPOT_WATCHER_ENABLED: bool
    IMDS_URL: str
    POLL_INTERVAL_SECONDS: float
    GRACE_PERIOD_SECONDS: int
    JOB_PROCESSING_SECONDS: int
    ALLOW_SIMULATE_INTERRUPTION: bool

    @staticmethod
    def _bool(env_name: str, default: bool) -> bool:
        v = os.getenv(env_name)
        if v is None:
            return default
        return v.strip().lower() in ("1", "true", "yes", "on")

    @classmethod
    def from_env(cls) -> "Config":
        db_path = os.getenv("DATABASE_URL", "data/jobs.db")
        return cls(
            DATABASE_URL=db_path,
            SPOT_WATCHER_ENABLED=cls._bool("SPOT_WATCHER_ENABLED", True),
            IMDS_URL=os.getenv(
                "IMDS_URL",
                "http://169.254.169.254/latest/meta-data/spot/instance-action",
            ),
            POLL_INTERVAL_SECONDS=float(os.getenv("POLL_INTERVAL_SECONDS", "5")),
            GRACE_PERIOD_SECONDS=int(os.getenv("GRACE_PERIOD_SECONDS", "110")),
            JOB_PROCESSING_SECONDS=int(os.getenv("JOB_PROCESSING_SECONDS", "10")),
            ALLOW_SIMULATE_INTERRUPTION=cls._bool("ALLOW_SIMULATE_INTERRUPTION", True),
        )

