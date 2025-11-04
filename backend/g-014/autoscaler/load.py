import time
from typing import Dict, Optional


class LoadModel:
    def __init__(self):
        self.global_rps: float = 0.0
        self.per_deployment_rps: Dict[str, float] = {}
        self._last_update = time.time()

    def set_rps(self, rps: float, deployment: Optional[str] = None):
        if deployment:
            self.per_deployment_rps[deployment] = max(0.0, rps)
        else:
            self.global_rps = max(0.0, rps)
        self._last_update = time.time()

    def get_rps(self, deployment: Optional[str] = None) -> float:
        if deployment and deployment in self.per_deployment_rps:
            return self.per_deployment_rps.get(deployment, 0.0)
        return self.global_rps

