import os
import yaml


def load_config(config_path: str | None = None) -> dict:
    # order: provided path -> ENV BACKUP_APP_CONFIG -> default ./config.yaml
    path = config_path or os.environ.get("BACKUP_APP_CONFIG") or os.path.join(os.getcwd(), "config.yaml")
    data = {}
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    # Allow simple ENV overrides
    # e.g., BACKUP_SCHEDULE_INTERVAL_SECONDS=3600
    try:
        interval_env = os.environ.get("BACKUP_SCHEDULE_INTERVAL_SECONDS")
        if interval_env:
            data.setdefault("backup", {})["schedule_interval_seconds"] = int(interval_env)
        retention_env = os.environ.get("RETENTION_SCHEDULE_INTERVAL_SECONDS")
        if retention_env:
            data.setdefault("retention", {})["schedule_interval_seconds"] = int(retention_env)
        drill_env = os.environ.get("DRILL_SCHEDULE_INTERVAL_SECONDS")
        if drill_env:
            data.setdefault("drill", {})["schedule_interval_seconds"] = int(drill_env)
    except Exception:
        pass
    return data

