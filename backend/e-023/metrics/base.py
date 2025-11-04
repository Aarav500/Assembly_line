from abc import ABC, abstractmethod


class MetricsSource(ABC):
    @abstractmethod
    def get_queue_depth(self, metric_id: str) -> int:
        raise NotImplementedError

