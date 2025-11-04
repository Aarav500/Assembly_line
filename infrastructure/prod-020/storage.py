import json
from typing import Any, Dict, List, Optional, Tuple

import redis

from config import REDIS_URL, DECISION_LOG_STREAM, EXPOSURE_LOG_STREAM, STREAM_MAXLEN


class RedisStorage:
    def __init__(self, url: str = REDIS_URL) -> None:
        self.r = redis.Redis.from_url(url, decode_responses=True)
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        # Ensure the index sets exist
        self.r.sadd("ff:flags", *[])
        self.r.sadd("ff:experiments", *[])

    # Flag operations
    def set_flag(self, name: str, config: Dict[str, Any]) -> None:
        key = f"ff:flag:{name}"
        self.r.set(key, json.dumps(config, separators=(",", ":")))
        self.r.sadd("ff:flags", name)

    def get_flag(self, name: str) -> Optional[Dict[str, Any]]:
        key = f"ff:flag:{name}"
        s = self.r.get(key)
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return None

    def list_flags(self) -> List[Dict[str, Any]]:
        names = sorted(self.r.smembers("ff:flags"))
        out: List[Dict[str, Any]] = []
        pipeline = self.r.pipeline()
        keys = [f"ff:flag:{n}" for n in names]
        for k in keys:
            pipeline.get(k)
        values = pipeline.execute()
        for n, raw in zip(names, values):
            if raw:
                try:
                    cfg = json.loads(raw)
                    out.append(cfg)
                except Exception:
                    pass
        return out

    # Experiment operations
    def set_experiment(self, name: str, config: Dict[str, Any]) -> None:
        key = f"ff:exp:{name}"
        self.r.set(key, json.dumps(config, separators=(",", ":")))
        self.r.sadd("ff:experiments", name)

    def get_experiment(self, name: str) -> Optional[Dict[str, Any]]:
        key = f"ff:exp:{name}"
        s = self.r.get(key)
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return None

    def list_experiments(self) -> List[Dict[str, Any]]:
        names = sorted(self.r.smembers("ff:experiments"))
        out: List[Dict[str, Any]] = []
        pipeline = self.r.pipeline()
        keys = [f"ff:exp:{n}" for n in names]
        for k in keys:
            pipeline.get(k)
        values = pipeline.execute()
        for n, raw in zip(names, values):
            if raw:
                try:
                    cfg = json.loads(raw)
                    out.append(cfg)
                except Exception:
                    pass
        return out

    # Logging operations
    def log_decision(self, payload: Dict[str, Any]) -> Optional[str]:
        try:
            return self.r.xadd(DECISION_LOG_STREAM, payload, maxlen=STREAM_MAXLEN, approximate=True)
        except Exception:
            return None

    def log_exposure(self, payload: Dict[str, Any]) -> Optional[str]:
        try:
            return self.r.xadd(EXPOSURE_LOG_STREAM, payload, maxlen=STREAM_MAXLEN, approximate=True)
        except Exception:
            return None

    # Utility
    def ping(self) -> bool:
        try:
            return bool(self.r.ping())
        except Exception:
            return False

