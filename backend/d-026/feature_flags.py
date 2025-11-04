import os
import json
import threading
import tempfile
import shutil
from typing import Any, Dict, List, Optional


def _normalize_key(k: str) -> str:
    return k.strip().lower().replace(" ", "_")


def _str2bool(val: str) -> Optional[bool]:
    if not isinstance(val, str):
        return None
    v = val.strip().lower()
    if v in ("1", "true", "yes", "y", "on"):  # truthy
        return True
    if v in ("0", "false", "no", "n", "off"):  # falsy
        return False
    return None


def _boolify(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        parsed = _str2bool(val)
        if parsed is not None:
            return parsed
        # Unrecognized string -> default
        return default
    return default


class EnvKV:
    def __init__(self, prefix: str = "FF_") -> None:
        self.prefix = prefix

    def _key_to_env(self, key: str) -> str:
        return f"{self.prefix}{_normalize_key(key).upper()}"

    def get(self, key: str) -> Optional[Any]:
        env_key = self._key_to_env(key)
        return os.environ.get(env_key)

    def all(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        plen = len(self.prefix)
        for k, v in os.environ.items():
            if k.startswith(self.prefix):
                out[_normalize_key(k[plen:])] = v
        return out


class FileKV:
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._ensure_file()
        self._data = self._read()

    def _ensure_file(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _read(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                # normalize keys
                return { _normalize_key(k): v for k, v in data.items() }
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}

    def _atomic_write(self, data: Dict[str, Any]) -> None:
        directory = os.path.dirname(self.path) or "."
        with self._lock:
            fd, tmp_path = tempfile.mkstemp(prefix="flags.", suffix=".json", dir=directory)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                    json.dump(data, tmp, indent=2, sort_keys=True)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                shutil.move(tmp_path, self.path)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

    def get(self, key: str) -> Optional[Any]:
        k = _normalize_key(key)
        with self._lock:
            return self._data.get(k)

    def set(self, key: str, value: Any) -> None:
        k = _normalize_key(key)
        with self._lock:
            self._data[k] = value
            self._atomic_write(self._data)

    def all(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)


class CompositeKV:
    def __init__(self, backends: List[Any]) -> None:
        self.backends = backends

    def get(self, key: str) -> Optional[Any]:
        for b in self.backends:
            try:
                v = b.get(key)
            except Exception:
                v = None
            if v is not None:
                return v
        return None

    def all(self) -> Dict[str, Any]:
        # lower precedence first, higher precedence overrides
        merged: Dict[str, Any] = {}
        for b in reversed(self.backends):
            try:
                items = b.all()
            except Exception:
                items = {}
            for k, v in items.items():
                merged[_normalize_key(k)] = v
        # flip back to final view
        # Now iterate in precedence order to override
        final: Dict[str, Any] = {}
        for b in self.backends:
            try:
                items = b.all()
            except Exception:
                items = {}
            for k, v in items.items():
                final[_normalize_key(k)] = v
        return final


class FeatureFlags:
    def __init__(self, kv: Any, default_enabled: bool = False) -> None:
        self.kv = kv
        self.default_enabled = default_enabled

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        v = self.kv.get(key)
        return default if v is None else v

    def enabled(self, key: str, default: Optional[bool] = None) -> bool:
        if default is None:
            default = self.default_enabled
        v = self.kv.get(key)
        if v is None:
            return bool(default)
        return _boolify(v, default=bool(default))

    def all(self) -> Dict[str, Any]:
        return self.kv.all()


# Flask helpers
from functools import wraps

def flag_required(name: str, default: bool = False, unauthorized_status: int = 404):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import current_app, abort
            flags: FeatureFlags = current_app.config.get("FEATURE_FLAGS")
            if not flags:
                abort(500)
            if not flags.enabled(name, default=default):
                abort(unauthorized_status)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def register_flask(app, flags: FeatureFlags) -> None:
    from flask import g
    app.config["FEATURE_FLAGS"] = flags

    @app.before_request
    def _inject_flags_to_g():
        g.feature_flags = flags

    @app.context_processor
    def _inject_flags_to_template():
        return {"feature_flags": flags}

