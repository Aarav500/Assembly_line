import logging
from typing import Dict

from providers.base import TrafficRouter

logger = logging.getLogger(__name__)


class FakeRouter(TrafficRouter):
    """
    A fake traffic router that logs intended operations. Useful for local testing.
    Keeps an in-memory view of service->(baseline, canary, weight).
    """

    def __init__(self):
        self._state: Dict[str, Dict[str, str | int]] = {}

    def set_traffic_split(self, service_name: str, baseline_version: str, canary_version: str, canary_weight: int) -> None:
        canary_weight = max(0, min(100, int(canary_weight)))
        self._state[service_name] = {
            "baseline": baseline_version,
            "canary": canary_version,
            "canary_weight": canary_weight,
        }
        logger.info("[router] %s: %s=%d%%, %s=%d%%", service_name, canary_version, canary_weight, baseline_version, 100 - canary_weight)

    def promote(self, service_name: str, new_version: str) -> None:
        st = self._state.get(service_name) or {}
        st["baseline"] = new_version
        st["canary"] = new_version
        st["canary_weight"] = 100
        self._state[service_name] = st
        logger.info("[router] %s: promoted %s to 100%%", service_name, new_version)

    def rollback(self, service_name: str, baseline_version: str) -> None:
        st = self._state.get(service_name) or {}
        st["baseline"] = baseline_version
        st["canary"] = baseline_version
        st["canary_weight"] = 0
        self._state[service_name] = st
        logger.info("[router] %s: rolled back to %s (100%%)", service_name, baseline_version)

