from __future__ import annotations
import time
from typing import Any, Dict, Iterable, Tuple


class PolicyManager:
    def __init__(self, cfg: Dict[str, Any]):
        self._cfg = cfg or {}

        # Auth
        self.require_auth: bool = bool(self._cfg.get("require_auth", False))
        auth_cfg = self._cfg.get("auth", {}) or {}
        self.auth_header: str = str(auth_cfg.get("header", "X-API-Key"))
        api_keys = auth_cfg.get("api_keys", []) or []
        self.api_keys = {k.strip() for k in api_keys if isinstance(k, str) and k.strip()}

        # Rate limit
        rl_cfg = self._cfg.get("rate_limit", {}) or {}
        self.rate_limit_enabled: bool = bool(rl_cfg.get("enabled", False))
        self.rate_limit_requests: int = int(rl_cfg.get("requests", 1000))
        self.rate_limit_window: int = int(rl_cfg.get("window_seconds", 60))

        # CORS
        allowed = self._cfg.get("allowed_origins", self._cfg.get("cors", {}).get("allowed_origins"))
        if allowed is None:
            allowed = []
        self.allowed_origins = []
        if isinstance(allowed, str):
            self.allowed_origins = [o.strip() for o in allowed.split(",") if o.strip()]
        elif isinstance(allowed, Iterable):
            self.allowed_origins = [str(o).strip() for o in allowed]

        # Feature flags
        self.feature_flags: Dict[str, bool] = {}
        for k, v in (self._cfg.get("feature_flags", {}) or {}).items():
            self.feature_flags[str(k)] = bool(v)

    def validate_api_key(self, key: str | None) -> bool:
        if not key:
            return False
        return key in self.api_keys

    def is_origin_allowed(self, origin: str) -> bool:
        if not self.allowed_origins:
            return False
        if "*" in self.allowed_origins:
            return True
        return origin in self.allowed_origins

    def flag_enabled(self, name: str) -> bool:
        return bool(self.feature_flags.get(name, False))


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, enabled: bool = True):
        self.max_requests = int(max_requests)
        self.window = float(window_seconds)
        self.enabled = bool(enabled)
        self._hits: dict[str, list[float]] = {}

    def hit(self, key: str) -> Tuple[bool, float | None]:
        if not self.enabled:
            return True, None
        now = time.time()
        window_start = now - self.window
        bucket = self._hits.setdefault(key, [])
        # Prune old timestamps
        i = 0
        for ts in bucket:
            if ts >= window_start:
                break
            i += 1
        if i:
            del bucket[:i]
        if len(bucket) < self.max_requests:
            bucket.append(now)
            return True, None
        # Compute retry-after until the oldest timestamp exits window
        oldest = bucket[0]
        retry_after = max(0.0, (oldest + self.window) - now)
        return False, retry_after

