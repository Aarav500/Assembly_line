import os
from dataclasses import dataclass
from typing import Dict, List, Tuple


def _parse_bool(val: str, default: bool) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_replica_dbs(val: str) -> List[Tuple[str, str]]:
    # Format: region|url,region|url
    replicas = []
    if not val:
        return replicas
    for part in val.split(','):
        part = part.strip()
        if not part:
            continue
        if '|' not in part:
            # if url only, region unknown
            replicas.append(("unknown", part))
        else:
            region, url = part.split('|', 1)
            replicas.append((region.strip(), url.strip()))
    return replicas


@dataclass
class Settings:
    region: str
    primary_url: str
    replica_dbs: List[Tuple[str, str]]  # list of (region, url)

    heartbeat_interval: float
    monitor_interval: float
    max_replica_lag_seconds: float
    read_strategy: str  # 'nearest' or 'lowest-lag'

    promotion_allowed: bool
    apply_schema_to_all: bool
    log_level: str


settings = Settings(
    region=os.getenv("REGION", "us-east-1"),
    primary_url=os.getenv(
        "PRIMARY_DATABASE_URL",
        # Example DSN: postgresql+psycopg2://user:pass@host:5432/db
        "postgresql+psycopg2://postgres:postgres@localhost:5432/primary_db",
    ),
    replica_dbs=_parse_replica_dbs(os.getenv(
        "REPLICA_DATABASES",
        # Example: "us-east-1|postgresql+psycopg2://user:pass@replica1:5432/db,eu-west-1|postgresql+psycopg2://user:pass@replica2:5432/db"
        "",
    )),
    heartbeat_interval=float(os.getenv("HEARTBEAT_INTERVAL", "1.0")),
    monitor_interval=float(os.getenv("MONITOR_INTERVAL", "2.0")),
    max_replica_lag_seconds=float(os.getenv("MAX_REPLICA_LAG_SECONDS", "5.0")),
    read_strategy=os.getenv("READ_STRATEGY", "nearest"),
    promotion_allowed=_parse_bool(os.getenv("PROMOTION_ALLOWED"), True),
    apply_schema_to_all=_parse_bool(os.getenv("APPLY_SCHEMA_TO_ALL"), True),
    log_level=os.getenv("LOG_LEVEL", "INFO"),
)

