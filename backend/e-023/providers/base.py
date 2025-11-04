from typing import Dict, Any
from abc import ABC, abstractmethod


class ComputeProvider(ABC):
    @abstractmethod
    def get_current_gpus(self, pool_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def scale_pool_to_gpus(self, pool_id: str, target_gpus: int) -> None:
        raise NotImplementedError

    def get_pool_metadata(self, pool_id: str) -> Dict[str, Any]:
        return {}

