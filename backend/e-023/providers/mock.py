import logging
from threading import RLock
from typing import Dict

from .base import ComputeProvider

logger = logging.getLogger(__name__)


class MockProvider(ComputeProvider):
    def __init__(self, initial: Dict[str, int] = None, scale_delay_seconds: int = 0):
        self._lock = RLock()
        self._pools = dict(initial or {})
        self._delay = max(0, int(scale_delay_seconds))

    def get_current_gpus(self, pool_id: str) -> int:
        with self._lock:
            return int(self._pools.get(pool_id, 0))

    def scale_pool_to_gpus(self, pool_id: str, target_gpus: int) -> None:
        with self._lock:
            logger.info("[MockProvider] Scaling pool %s to %s GPUs", pool_id, target_gpus)
            self._pools[pool_id] = int(target_gpus)

    def get_pool_metadata(self, pool_id: str):
        return {
            'provider': 'mock',
            'pool_id': pool_id,
        }

