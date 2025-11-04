import os
from datetime import timedelta


def _get_env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def _get_env_float(name: str, default: float) -> float:
    val = os.getenv(name)
    try:
        return float(val) if val is not None else default
    except Exception:
        return default


def _get_env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    try:
        return int(val) if val is not None else default
    except Exception:
        return default


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Detector configuration
    DETECTOR_ENABLED = _get_env_bool("DETECTOR_ENABLED", True)
    DETECTOR_POLL_SECONDS = _get_env_int("DETECTOR_POLL_SECONDS", 30)

    # Regression thresholds (defaults)
    REGRESSION_PCT_THRESHOLD = _get_env_float("REGRESSION_PCT_THRESHOLD", 0.2)  # 20%
    REGRESSION_Z_THRESHOLD = _get_env_float("REGRESSION_Z_THRESHOLD", 2.0)
    BASELINE_WINDOW_MIN = _get_env_int("BASELINE_WINDOW_MIN", 60)
    EVAL_WINDOW_MIN = _get_env_int("EVAL_WINDOW_MIN", 10)
    BASELINE_MIN_SAMPLES = _get_env_int("BASELINE_MIN_SAMPLES", 30)
    EVAL_MIN_SAMPLES = _get_env_int("EVAL_MIN_SAMPLES", 5)

    # GitHub integration
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO = os.getenv("GITHUB_REPO", "")  # format: owner/repo

    PORT = os.getenv("PORT", 5000)

