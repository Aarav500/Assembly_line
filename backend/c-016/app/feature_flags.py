import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, Optional

from flask import abort, current_app, g

ISO = "%Y-%m-%dT%H:%M:%SZ"


def utcnow_iso() -> str:
    return datetime.utcnow().strftime(ISO)


class FeatureFlagStore:
    def __init__(self, path: str):
        self._path = path
        self._flags: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def load(self) -> None:
        with self._lock:
            directory = os.path.dirname(self._path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            if not os.path.exists(self._path):
                # Initialize empty file
                self._flags = {}
                self._atomic_write(self._flags)
                return
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._flags = data
                    else:
                        self._flags = {}
            except Exception:
                # Corrupt or unreadable file; start fresh in memory (do not overwrite file yet)
                self._flags = {}

    def _atomic_write(self, data: Dict[str, Any]) -> None:
        tmp_path = f"{self._path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as tmp:
            json.dump(data, tmp, indent=2, sort_keys=True)
            tmp.write("\n")
        os.replace(tmp_path, self._path)

    def save(self) -> None:
        with self._lock:
            self._atomic_write(self._flags)

    def all(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {k: dict(v) for k, v in self._flags.items()}

    def get_record(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            rec = self._flags.get(name)
            return dict(rec) if rec is not None else None

    def is_enabled(self, name: str, default: bool = False, overrides: Optional[Dict[str, bool]] = None) -> bool:
        if overrides and name in overrides:
            return bool(overrides[name])
        with self._lock:
            rec = self._flags.get(name)
            if rec is None:
                return bool(default)
            return bool(rec.get("enabled", default))

    def set(self, name: str, enabled: bool, description: Optional[str] = None, expires_on: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            now = utcnow_iso()
            rec = self._flags.get(name)
            if rec is None:
                rec = {
                    "enabled": bool(enabled),
                    "description": description or "",
                    "created_at": now,
                    "updated_at": now,
                    "expires_on": expires_on or None,
                }
                self._flags[name] = rec
            else:
                rec["enabled"] = bool(enabled)
                if description is not None:
                    rec["description"] = description
                rec["updated_at"] = now
                rec["expires_on"] = expires_on if expires_on is not None else rec.get("expires_on")
            self.save()
            return dict(rec)


def require_flag(name: str, default: bool = False, status_code: int = 404):
    def decorator(func):
        from functools import wraps

        @wraps(func)
        def wrapper(*args, **kwargs):
            store: FeatureFlagStore = current_app.extensions["feature_flags"]
            overrides = getattr(g, "flag_overrides", None)
            if not store.is_enabled(name, default=default, overrides=overrides):
                abort(status_code)
            return func(*args, **kwargs)

        return wrapper

    return decorator

