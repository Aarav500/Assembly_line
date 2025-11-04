from __future__ import annotations
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Deque, Tuple, List, Dict

from models import CanaryConfig


@dataclass
class MetricSample:
    timestamp: float
    requests: int
    error_rate: Optional[float] = None  # 0..1
    errors: Optional[int] = None
    latency_p95_ms: Optional[float] = None
    availability: Optional[float] = None  # 0..1
    cpu_utilization: Optional[float] = None  # 0..1

    @staticmethod
    def from_dict(d: dict, ts: Optional[float] = None) -> "MetricSample":
        if ts is None:
            ts = d.get("timestamp") or time.time()
        requests = int(d.get("requests") or 0)
        errors = d.get("errors")
        error_rate = d.get("error_rate")
        if error_rate is None and errors is not None and requests:
            error_rate = float(errors) / max(1, requests)
        latency = d.get("latency_p95_ms")
        availability = d.get("availability")
        cpu = d.get("cpu_utilization")
        return MetricSample(
            timestamp=float(ts),
            requests=requests,
            errors=(int(errors) if errors is not None else None),
            error_rate=(float(error_rate) if error_rate is not None else None),
            latency_p95_ms=(float(latency) if latency is not None else None),
            availability=(float(availability) if availability is not None else None),
            cpu_utilization=(float(cpu) if cpu is not None else None),
        )


class MetricsWindow:
    def __init__(self, window_sec: int = 60):
        self.window_sec = window_sec
        self.samples: Deque[MetricSample] = deque()

    def add_sample(self, sample: MetricSample):
        self.samples.append(sample)
        self._prune(sample.timestamp)

    def _prune(self, now: float):
        cutoff = now - self.window_sec
        while self.samples and self.samples[0].timestamp < cutoff:
            self.samples.popleft()

    def is_sufficient(self, min_samples: int, min_requests: int) -> bool:
        if len(self.samples) < min_samples:
            return False
        total_req = sum(s.requests for s in self.samples)
        return total_req >= min_requests

    def reset(self):
        self.samples.clear()

    def aggregate(self) -> Dict[str, float]:
        if not self.samples:
            return {}
        total_req = sum(s.requests for s in self.samples)
        # Weighted metrics by requests where applicable
        agg: Dict[str, float] = {
            "window_samples": float(len(self.samples)),
            "window_requests": float(total_req),
        }
        # Error rate
        err_rate = None
        if total_req > 0:
            total_errors = 0.0
            have_any = False
            for s in self.samples:
                if s.errors is not None:
                    total_errors += s.errors
                    have_any = True
                elif s.error_rate is not None:
                    total_errors += s.error_rate * s.requests
                    have_any = True
            if have_any:
                err_rate = total_errors / max(1.0, total_req)
                agg["error_rate"] = float(err_rate)
        # Latency p95 (approximate: average of samples)
        lat_vals = [s.latency_p95_ms for s in self.samples if s.latency_p95_ms is not None]
        if lat_vals:
            agg["latency_p95_ms"] = float(sum(lat_vals) / len(lat_vals))
        # Availability (weighted by requests)
        avail_vals = [s.availability for s in self.samples if s.availability is not None]
        if avail_vals and total_req > 0:
            num = 0.0
            denom = 0.0
            for s in self.samples:
                if s.availability is not None:
                    num += s.availability * max(1, s.requests)
                    denom += max(1, s.requests)
            if denom > 0:
                agg["availability"] = float(num / denom)
        # CPU utilization (simple mean)
        cpu_vals = [s.cpu_utilization for s in self.samples if s.cpu_utilization is not None]
        if cpu_vals:
            agg["cpu_utilization"] = float(sum(cpu_vals) / len(cpu_vals))
        return agg

    def evaluate(self, policy: CanaryConfig) -> Tuple[bool, List[str], Dict[str, float]]:
        agg = self.aggregate()
        violations: List[str] = []
        # Check thresholds only if provided
        if policy.max_error_rate is not None and "error_rate" in agg:
            if agg["error_rate"] > policy.max_error_rate:
                violations.append(f"error_rate {agg['error_rate']:.4f} > {policy.max_error_rate:.4f}")
        if policy.max_latency_p95_ms is not None and "latency_p95_ms" in agg:
            if agg["latency_p95_ms"] > policy.max_latency_p95_ms:
                violations.append(f"latency_p95_ms {agg['latency_p95_ms']:.1f} > {policy.max_latency_p95_ms:.1f}")
        if policy.min_availability is not None and "availability" in agg:
            if agg["availability"] < policy.min_availability:
                violations.append(f"availability {agg['availability']:.4f} < {policy.min_availability:.4f}")
        if policy.max_cpu_utilization is not None and "cpu_utilization" in agg:
            if agg["cpu_utilization"] > policy.max_cpu_utilization:
                violations.append(f"cpu_utilization {agg['cpu_utilization']:.3f} > {policy.max_cpu_utilization:.3f}")
        passed = len(violations) == 0
        return passed, violations, agg

