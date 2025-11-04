from typing import Any, Dict, List


class ProvisionError(Exception):
    pass


class Provider:
    name = "base"
    label = "Base Provider"

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
        raise NotImplementedError

    def list_instances(self) -> List[Dict[str, Any]]:
        return []

    def capabilities(self) -> Dict[str, Any]:
        return {
            "user_data": True,
            "tags": False,
            "volumes": False,
            "networks": True,
        }

