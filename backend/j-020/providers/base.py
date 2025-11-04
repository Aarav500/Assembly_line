from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class ProviderError(Exception):
    pass

class BaseProvider(ABC):
    def __init__(self, data_dir: str, templates_dir: str):
        self.data_dir = data_dir
        self.templates_dir = templates_dir

    @abstractmethod
    def provision(self, sandbox_id: str, template: str, env: Dict[str, str]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def teardown(self, sandbox_id: str, provider_data: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def status(self, sandbox_id: str, provider_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def stop(self, sandbox_id: str, provider_data: Dict[str, Any]) -> None:
        raise NotImplementedError

    def start(self, sandbox_id: str, provider_data: Dict[str, Any]) -> None:
        raise NotImplementedError

