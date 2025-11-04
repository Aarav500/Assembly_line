import json
import os
import threading
from pathlib import Path

_LOCK = threading.Lock()
_CONFIG_PATH = Path(os.environ.get("TRAFFIC_CONFIG", "config/traffic.json"))
_DEFAULT = {
    "blue_percent": 100,
    "respect_sticky": True,
    "cookie_max_age": 7 * 24 * 3600
}


def _ensure_file():
    if not _CONFIG_PATH.parent.exists():
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _CONFIG_PATH.exists():
        save_config(_DEFAULT.copy())


def get_config() -> dict:
    _ensure_file()
    with _LOCK:
        try:
            data = json.loads(_CONFIG_PATH.read_text())
        except Exception:
            data = _DEFAULT.copy()
    # Normalize
    data["blue_percent"] = int(max(0, min(100, data.get("blue_percent", 100))))
    data["respect_sticky"] = bool(data.get("respect_sticky", True))
    data["cookie_max_age"] = int(data.get("cookie_max_age", 7 * 24 * 3600))
    return data


def save_config(cfg: dict):
    with _LOCK:
        tmp_path = _CONFIG_PATH.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(cfg, indent=2, sort_keys=True))
        tmp_path.replace(_CONFIG_PATH)


def set_split(blue_percent: int):
    cfg = get_config()
    cfg["blue_percent"] = int(max(0, min(100, blue_percent)))
    save_config(cfg)


def set_all(version: str):
    v = (version or "").lower()
    if v not in ("blue", "green"):
        raise ValueError("version must be 'blue' or 'green'")
    cfg = get_config()
    cfg["blue_percent"] = 100 if v == "blue" else 0
    save_config(cfg)


def toggle() -> int:
    cfg = get_config()
    blue_percent = int(cfg.get("blue_percent", 100))
    new_percent = 0 if blue_percent >= 50 else 100
    cfg["blue_percent"] = new_percent
    save_config(cfg)
    return new_percent


def set_respect_sticky(respect: bool):
    cfg = get_config()
    cfg["respect_sticky"] = bool(respect)
    save_config(cfg)


def set_cookie_max_age(max_age: int):
    cfg = get_config()
    cfg["cookie_max_age"] = int(max(0, max_age))
    save_config(cfg)

