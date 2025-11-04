from collections import defaultdict, deque
from datetime import datetime
from typing import List, Dict, Any


class LogBuffer:
    def __init__(self, capacity_per_service: int = 500):
        self.capacity_per_service = capacity_per_service
        self._buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.capacity_per_service))

    def add(self, service: str, level: str, message: str, **context):
        entry = {
            'ts': datetime.utcnow().isoformat() + 'Z',
            'level': level.upper(),
            'message': message,
            'context': context or {}
        }
        self._buffers[service].append(entry)

    def tail(self, service: str, n: int = 50) -> List[Dict[str, Any]]:
        buf = self._buffers.get(service)
        if not buf:
            return []
        return list(buf)[-n:]

    def snapshot_all(self, last_n: int = 50) -> Dict[str, list]:
        return {svc: list(buf)[-last_n:] for svc, buf in self._buffers.items()}

