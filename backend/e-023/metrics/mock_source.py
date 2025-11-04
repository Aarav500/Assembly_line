import time
import math
from .base import MetricsSource


class MockMetrics(MetricsSource):
    def __init__(self, mode: str = 'fixed', value: int = 0, min: int = 0, max: int = 100, period_seconds: int = 300, sequence=None):
        self.mode = mode
        self.fixed = int(value)
        self.min = int(min)
        self.max = int(max)
        self.period = max(1, int(period_seconds))
        self.sequence = list(sequence or [])
        self._start = time.time()

    def get_queue_depth(self, metric_id: str) -> int:
        if self.mode == 'fixed':
            return self.fixed
        if self.mode == 'sequence':
            if not self.sequence:
                return 0
            idx = int((time.time() - self._start) // 5) % len(self.sequence)
            return int(self.sequence[idx])
        if self.mode == 'sine':
            t = time.time() - self._start
            amp = (self.max - self.min) / 2.0
            mid = (self.max + self.min) / 2.0
            val = mid + amp * math.sin(2 * math.pi * (t / self.period))
            return max(self.min, min(self.max, int(val)))
        # default: triangular
        t = (time.time() - self._start) % self.period
        half = self.period / 2.0
        if t <= half:
            val = self.min + (self.max - self.min) * (t / half)
        else:
            val = self.max - (self.max - self.min) * ((t - half) / half)
        return int(val)

