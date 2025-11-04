import os
from dataclasses import dataclass


def _get_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).lower() in {"1", "true", "t", "yes", "y", "on"}


@dataclass
class Settings:
    host: str = os.getenv("APP_HOST", "0.0.0.0")
    port: int = int(os.getenv("APP_PORT", "8000"))
    debug: bool = _get_bool("APP_DEBUG", False)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Trackers
    default_tracker: str = os.getenv("DEFAULT_TRACKER", "mlflow")
    default_experiment: str = os.getenv("DEFAULT_EXPERIMENT", "demo-flask-tracker")

    # MLflow
    mlflow_tracking_uri: str | None = os.getenv("MLFLOW_TRACKING_URI")

    # Weights & Biases
    wandb_project: str = os.getenv("WANDB_PROJECT", "demo-flask-tracker")
    wandb_mode: str | None = os.getenv("WANDB_MODE")  # e.g., "offline" or "online"


settings = Settings()


def setup_integrations():
    # Configure MLflow tracking URI if provided
    try:
        import mlflow
        if settings.mlflow_tracking_uri:
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    except Exception:
        # If mlflow not installed or any misconfiguration occurs, ignore here; it will surface when used
        pass

    # Configure W&B mode
    if settings.wandb_mode:
        os.environ["WANDB_MODE"] = settings.wandb_mode

