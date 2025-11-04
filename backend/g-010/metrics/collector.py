import threading
import time
from collections import deque
from typing import Dict, Any


class _Entry:
    def __init__(self, max_samples: int = 2000):
        self.total_requests = 0
        self.success = 0
        self.errors = 0
        self.latencies = deque(maxlen=max_samples)


class MetricsCollector:
    def __init__(self, max_latency_samples: int = 2000):
        self._lock = threading.RLock()
        self._by_version: Dict[str, _Entry] = {}
        self._max_samples = max_latency_samples
        self._start_time = time.time()

    def record(self, version: str, success: bool, latency_ms: float):
        with self._lock:
            entry = self._by_version.get(version)
            if entry is None:
                entry = _Entry(max_samples=self._max_samples)
                self._by_version[version] = entry
            entry.total_requests += 1
            if success:
                entry.success += 1
            else:
                entry.errors += 1
            entry.latencies.append(float(latency_ms))

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            per_version = {}
            for v, e in self._by_version.items():
                lat = list(e.latencies)
                lat_sorted = sorted(lat)
                n = len(lat_sorted)
                def pct(p):
                    if n == 0:
                        return None
                    k = max(0, min(n - 1, int(round((p / 100.0) * (n - 1)))))
                    return round(lat_sorted[k], 2)
                per_version[v] = {
                    "total_requests": e.total_requests,
                    "success": e.success,
                    "errors": e.errors,
                    "error_rate": round((e.errors / e.total_requests), 4) if e.total_requests else 0.0,
                    "latency_ms": {
                        "p50": pct(50),
                        "p90": pct(90),
                        "p95": pct(95),
                        "p99": pct(99),
                        "avg": round(sum(lat) / n, 2) if n else None,
                    },
                }
            up_seconds = int(time.time() - self._start_time)
            return {
                "uptime_sec": up_seconds,
                "per_version": per_version,
            }

