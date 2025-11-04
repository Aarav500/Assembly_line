import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from typing import Any, Dict
import yaml
from datetime import datetime, timezone


_config_cache: Dict[str, Any] | None = None
_config_lock = threading.Lock()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config(path: str = None) -> Dict[str, Any]:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    with _config_lock:
        if _config_cache is not None:
            return _config_cache
        config_path = path or os.environ.get("HC_CONFIG", "config.yaml")
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _config_cache = data
        return data


def get_admin_token(config: Dict[str, Any]) -> str | None:
    env_name = (config.get("app", {}) or {}).get("admin_token_env", "ADMIN_TOKEN")
    return os.environ.get(env_name)


def setup_logger(config: Dict[str, Any]) -> logging.Logger:
    log_level_str = (config.get("app", {}) or {}).get("log_level", "INFO").upper()
    level = getattr(logging, log_level_str, logging.INFO)
    logger = logging.getLogger("health_orchestrator")
    logger.setLevel(level)
    if logger.handlers:
        return logger
    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    log_file = (config.get("app", {}) or {}).get("log_file")
    if log_file:
        try:
            file_handler = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3)
            file_handler.setLevel(level)
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Failed to set up file logging: {e}")
    return logger

