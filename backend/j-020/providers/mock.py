from typing import Dict, Any
from datetime import datetime
from .base import BaseProvider

class MockProvider(BaseProvider):
    def provision(self, sandbox_id: str, template: str, env: Dict[str, str]) -> Dict[str, Any]:
        return {
            "template": template,
            "env": env,
            "mock": True,
            "provisioned_at": datetime.utcnow().isoformat() + "Z",
            "ports": [{"service": "dummy", "host_ip": "127.0.0.1", "host_port": 0, "container_port": 0, "protocol": "tcp"}],
        }

    def teardown(self, sandbox_id: str, provider_data: Dict[str, Any]) -> None:
        return

    def status(self, sandbox_id: str, provider_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"state": "running", "services": [{"name": "dummy", "state": "running"}], "ports": provider_data.get("ports", [])}

    def stop(self, sandbox_id: str, provider_data: Dict[str, Any]) -> None:
        return

    def start(self, sandbox_id: str, provider_data: Dict[str, Any]) -> None:
        return

