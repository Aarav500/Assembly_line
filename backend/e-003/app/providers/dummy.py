import time
import uuid
from typing import Any, Dict, List

from .base import Provider


class DummyProvider(Provider):
    name = "dummy"
    label = "Dummy Provider (Simulator)"

    def __init__(self) -> None:
        self._instances: Dict[str, Dict[str, Any]] = {}

    def create_instance(
        self,
        name: str,
        image: str,
        instance_type: str,
        network: Dict[str, Any],
        ssh_key: str,
        cloud_init: str,
        extra: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        inst_id = str(uuid.uuid4())
        ip_octet = (len(self._instances) % 200) + 10
        instance = {
            "id": inst_id,
            "name": name or f"vm-{inst_id[:8]}",
            "status": "running",
            "image": image or "generic",
            "instance_type": instance_type or "t3.micro",
            "ip": f"10.0.0.{ip_octet}",
            "created_at": int(time.time()),
            "provider": self.name,
            "network": network or {},
            "ssh_key": ssh_key,
            "cloud_init_preview": cloud_init[:4000],
        }
        self._instances[inst_id] = instance
        return instance

    def list_instances(self) -> List[Dict[str, Any]]:
        return list(self._instances.values())

