from collections import deque
from typing import Dict, Any, List
import threading


class SampleBuffer:
    def __init__(self, maxlen: int = 500):
        self._dq = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def add_sample(self, features: Dict[str, Any], prediction: float):
        with self._lock:
            self._dq.append({'features': features, 'prediction': prediction})

    def get_samples(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._dq)

    def size(self) -> int:
        with self._lock:
            return len(self._dq)

