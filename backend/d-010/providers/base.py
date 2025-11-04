from __future__ import annotations
from abc import ABC, abstractmethod


class TrafficRouter(ABC):
    @abstractmethod
    def set_traffic_split(self, service_name: str, baseline_version: str, canary_version: str, canary_weight: int) -> None:
        """Route canary_weight percent to canary_version, remainder to baseline_version."""
        raise NotImplementedError

    @abstractmethod
    def promote(self, service_name: str, new_version: str) -> None:
        """Promote canary to 100% of traffic."""
        raise NotImplementedError

    @abstractmethod
    def rollback(self, service_name: str, baseline_version: str) -> None:
        """Route 100% of traffic to baseline_version."""
        raise NotImplementedError

